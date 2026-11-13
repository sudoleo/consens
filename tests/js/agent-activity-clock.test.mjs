import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// "Working for 9s" ticks in a field of fixed width: the chevron and the
// model icons after it stay put while it counts and when it ends. The words
// themselves do not change.
describe("activity clock", () => {
  it("keeps its words and sizes its time slot by unit, with the other verb reserved", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    activity.render(host, { running: true, elapsedMs: 9000, status: "running", events: [] });
    const title = host.querySelector(".agent-activity-title");
    const time = title.querySelector(".agent-activity-time");
    const verb = title.querySelector(".agent-activity-verb");
    expect(title.textContent).toBe("Working for 9s");
    // The first minute holds only the seconds slot: the minutes slot left a
    // wide gap before the chevron.
    expect(time.dataset.unit).toBe("seconds");
    expect(verb.dataset.ghost).toBe("Thought for");
    activity.render(host, { running: true, elapsedMs: 10000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 10s");
    expect(time.dataset.unit).toBe("seconds");
    expect(title.querySelector(".agent-activity-time")).toBe(time);
    activity.render(host, { running: true, elapsedMs: 72000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 1m 12s");
    expect(time.dataset.unit).toBe("minutes");
    activity.render(host, { running: false, elapsedMs: 72000, status: "succeeded", events: [] });
    expect(title.textContent).toBe("Thought for 1m 12s");
    expect(time.dataset.unit).toBe("minutes");
    // Its clock is still: the field takes its own words, no double gap.
    expect(verb.dataset.ghost).toBeUndefined();
    activity.render(host, { running: false, elapsedMs: 72000, status: "failed", events: [] });
    expect(title.textContent).toBe("Failed after 1m 12s");
    expect(verb.dataset.ghost).toBeUndefined();
    activity.dispose(host);
    // A saved turn that never ticked here sizes the slot by its own value.
    const saved = app.document.createElement("div");
    activity.render(saved, { running: false, elapsedMs: 18000, status: "succeeded", events: [] });
    expect(saved.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    vi.useRealTimers();
    app.dom.window.close();
  });

  it("ends a short run in the seconds slot and lets a later end widen it once", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="short"></div><div id="edge"></div>' });
    const activity = app.window.App.agentActivity;
    const short = app.document.getElementById("short");
    activity.render(short, { running: true, elapsedMs: 40000, status: "running", events: [] });
    activity.render(short, { running: false, elapsedMs: 41000, status: "succeeded", events: [] });
    expect(short.querySelector(".agent-activity-title").textContent).toBe("Thought for 41s");
    expect(short.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    // The server's end can land past the minute the browser last showed.
    const edge = app.document.getElementById("edge");
    activity.render(edge, { running: true, elapsedMs: 59000, status: "running", events: [] });
    expect(edge.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    activity.render(edge, { running: false, elapsedMs: 60400, status: "succeeded", events: [] });
    expect(edge.querySelector(".agent-activity-title").textContent).toBe("Thought for 1m 0s");
    expect(edge.querySelector(".agent-activity-time").dataset.unit).toBe("minutes");
    activity.dispose(short);
    activity.dispose(edge);
    vi.useRealTimers();
    app.dom.window.close();
  });
});

// One state everywhere: while the reviewers check the answer
// the head said "Working for", and while the run waited for the user its
// clock ran on.
describe("activity head while the run reviews or waits", () => {
  it("says Reviewing while the reviewers check, and stands still while it waits for the user", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    // The page's wall clock, as the caller's elapsed time counts it.
    let wall = Date.parse("2026-10-29T10:00:00Z");
    app.window.Date.now = () => wall;
    const advance = ms => { wall += ms; vi.advanceTimersByTime(ms); };
    const title = () => host.querySelector(".agent-activity-title").textContent;
    activity.render(host, { running: true, elapsedMs: 139000, status: "running", events: [],
      review: { mode: "audit", status: "running" }, answerText: "The answer." });
    expect(title()).toBe("Reviewing · 2m 19s");
    expect(host.querySelector(".agent-activity-verb").dataset.ghost).toBeUndefined();
    // The comparison mode has no answer check: a review without the
    // reviewers' mode is no phase of its own.
    activity.render(host, { running: true, elapsedMs: 139000, status: "running", events: [],
      review: { status: "running" }, answerText: "The answer." });
    expect(title()).toBe("Working for 2m 19s");
    expect(activity.PHASE_WORDS.checking).toBeUndefined();
    // A pause: the head says so, and its clock does not move while it lasts.
    const hold = { version: 1, kind: "hold", id: "hold-a1", step_id: "hold", reviewer: "Claude", halt: "harm",
      reason: "Deletes files.", state: "waiting" };
    activity.render(host, { running: true, elapsedMs: 150000, status: "running", events: [hold] });
    expect(title()).toBe("Paused · 2m 30s");
    advance(4000);
    activity.render(host, { running: true, elapsedMs: 154000, status: "running", events: [hold] });
    expect(title()).toBe("Paused · 2m 30s");
    // The agent's own question waits for the user too.
    const ask = { ...hold, id: "hold-a2", ask: "browser", request: "Log in.", reviewer: "", halt: "" };
    activity.render(host, { running: true, elapsedMs: 154000, status: "running", events: [ask] });
    expect(title()).toBe("Waiting for you · 2m 30s");
    // Decided: it works on from where it stood, without the time it waited.
    advance(6000);
    activity.render(host, { running: true, elapsedMs: 160000, status: "running", events: [{ ...ask, state: "handed_back" }] });
    expect(title()).toBe("Working for 2m 30s");
    activity.dispose(host);
    vi.useRealTimers();
    app.dom.window.close();
  });

  it("leaves the time a saved turn waited for the user out of its duration", () => {
    const app = loadScripts(["static/js/agent-activity.js"], { body: "" });
    const { savedDuration } = app.window.App.agentActivity;
    const turn = { created_at: "2026-10-29T10:00:00Z", completed_at: "2026-10-29T10:32:10Z" };
    expect(savedDuration(turn)).toBe(1930000);
    expect(savedDuration({ ...turn, agent_wait_seconds: 1810.5 })).toBe(119500);
    expect(savedDuration({ ...turn, agent_wait_seconds: "1810" })).toBe(1930000);
    app.dom.window.close();
  });
});

// On the German page "{0} reasoning" took the whole line, model name
// included, and the line was written anew on every render.
describe("run details on a German page", () => {
  it("translates the reasoning on its own, keeps the model's name and the line", async () => {
    const app = loadScripts(["static/js/i18n.js", "static/js/app-text.js", "static/js/agent-activity.js"], {
      body: '<div id="host"></div>', base: false,
      before(window) {
        window.__consensI18n = { lang: "de", entries: {
          "{0} reasoning": "Nachdenken: {0}", "High": "Hoch", "Reasoning off": "Nachdenken aus" } };
      },
    });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    const settled = async () => { await Promise.resolve(); app.window.App.i18n.flush(); };
    const settings = { label: "Claude Sonnet 5.5", reasoning_effort: "high" };
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [], settings });
    await settled();
    const details = host.querySelector(".agent-activity-run-details");
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken: Hoch");
    const name = details.firstElementChild;
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [], settings });
    await settled();
    expect(details.firstElementChild).toBe(name);
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken: Hoch");
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [],
      settings: { label: "Claude Sonnet 5.5", reasoning_effort: "none" } });
    await settled();
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken aus");
    app.dom.window.close();
  });
});

// Settings › Agent › Pass notes to the agent: the review and the agent's pass
// over its notes go on after the answer stood, and a sentence may still
// change. The head says so up there, where the reader looks, instead of
// "Thought for", and then what came of it; its time stays the time until the
// answer stood. Without the setting the head is as it always was.
describe("activity head of an answer whose check goes on after it stood", () => {
  const boot = () => {
    const app = loadScripts(["static/js/agent-review.js", "static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    return { app, host: app.document.getElementById("host"), activity: app.window.App.agentActivity };
  };
  const note = (text, finding) => ({ model: "DeepSeek", kind: "doubtful", note: text, finding });
  function review({ status = "succeeded", feedback } = {}) {
    const claims = [
      { anchor: "First.", kind: "doubtful", audit: true, agree: [], dissent: [{ ...note("One.", "s1"), mark: 1 }] },
      { anchor: "Second.", kind: "doubtful", audit: true, agree: [], dissent: [{ ...note("Two.", "s2"), mark: 2 }] }];
    return { mode: "audit", status, answer_version: 1, answer_hash: "h", versions: [{ id: 1, text: "First. Second.", hash: "h" }],
      audit: { reviewers: [{ provider: "deepseek", provider_label: "DeepSeek", status: status === "running" ? "running" : "completed" }],
        claims, unplaced: [], process: [], ...(feedback ? { feedback } : {}) } };
  }
  const findings = (state, extra = {}) => [
    { id: "s1", on: "answer", kind: "doubtful", voices: 1, hard: false, state, notes: [note("One.")], ...extra },
    { id: "s2", on: "answer", kind: "doubtful", voices: 1, hard: false, state, notes: [note("Two."), note("Too.")], ...extra }];
  const head = host => host.querySelector(".agent-activity-title").textContent;

  it("says the answer is still being checked, then what came of it, at the time it stood", () => {
    const { app, host, activity } = boot();
    const render = (rev, ended) => activity.render(host, { running: false, status: "succeeded", elapsedMs: 14300, events: [],
      review: rev, reviewEnded: ended });
    render(review({ status: "running", feedback: { status: "live", findings: findings("open") } }), false);
    expect(head(host)).toBe("Answer in 14s · checking…");
    expect(host.querySelector(".agent-activity").classList.contains("has-check-note")).toBe(true);
    // Each phrase alone for the translation.
    expect([...host.querySelectorAll(".agent-activity-after > span")].map(span => span.textContent)).toEqual(["checking…"]);
    render(review({ feedback: { status: "checking", findings: findings("checking", { delivered: "final" }) } }), false);
    expect(head(host)).toBe("Answer in 14s · checking 3 notes…");
    const one = review({ feedback: { status: "checking", findings: findings("checking", { delivered: "final" }).slice(0, 1) } });
    render(one, false);
    expect(head(host)).toBe("Answer in 14s · checking 1 note…");
    // Settled: the one thing that came of it; the rest stands under the answer.
    const improved = review({ feedback: { status: "done", findings: [
      { ...findings("corrected", { delivered: "final" })[0], before: "First.", after: "First, fixed." },
      { ...findings("disputed", { delivered: "final" })[1], reason: "It stands." }] } });
    improved.audit.claims = improved.audit.claims.slice(1);
    render(improved, true);
    expect(head(host)).toBe("Answer in 14s · checked · 1 sentence improved");
    expect([...host.querySelectorAll(".agent-activity-after > span")].map(span => span.textContent))
      .toEqual(["checked", "1 sentence improved"]);
    render(review({ feedback: { status: "done", findings: findings("disputed", { delivered: "final", reason: "So." }) } }), true);
    expect(head(host)).toBe("Answer in 14s · checked · 2 notes open");
    const quiet = review({ feedback: { status: "done", findings: [] } });
    quiet.audit.claims = [];
    render(quiet, true);
    expect(head(host)).toBe("Answer in 14s · checked · no objections");
    render(review({ feedback: { status: "done", skipped: "failed", findings: findings("open", { delivered: "final" }) } }), true);
    expect(head(host)).toBe("Answer in 14s · checked · correction not possible");
    render(review({ feedback: { status: "done", skipped: "stopped", findings: findings("open", { delivered: "final" }) } }), true);
    expect(head(host)).toBe("Answer in 14s · checked · correction stopped");
    // A run that ended in the middle of the pass: what the review has.
    render(review({ feedback: { status: "checking", findings: findings("checking", { delivered: "final" }) } }), true);
    expect(head(host)).toBe("Answer in 14s · checked · 2 notes open");
    // A review that did not finish: the head says what it always said.
    render(review({ status: "failed", feedback: { status: "done", findings: [] } }), true);
    expect(head(host)).toBe("Thought for 14s");
    expect(host.querySelector(".agent-activity-after")).toBeNull();
    expect(host.querySelector(".agent-activity").classList.contains("has-check-note")).toBe(false);
    app.dom.window.close();
  });

  it("leaves the head of a review without the setting as it was, also while that review runs", () => {
    const today = boot(), live = boot();
    today.activity.render(today.host, { running: false, status: "succeeded", elapsedMs: 14300, events: [], review: review({ status: "running" }) });
    live.activity.render(live.host, { running: false, status: "succeeded", elapsedMs: 14300, events: [], review: review({ status: "running" }),
      reviewEnded: false });
    expect(head(live.host)).toBe("Thought for 14s");
    expect(live.host.innerHTML).toBe(today.host.innerHTML);
    today.app.dom.window.close();
    live.app.dom.window.close();
  });

  it("counts a saved turn until its answer stood, never the review after it", () => {
    const { app, activity } = boot();
    const turn = { created_at: "2026-11-13T17:00:00.000Z", agent_answer_fixed_at: "2026-11-13T17:00:14.300Z",
      completed_at: "2026-11-13T17:00:32.500Z", agent_review: review({ feedback: { status: "done", findings: [] } }) };
    expect(activity.savedDuration(turn)).toBe(14300);
    // Without the setting the turn's end counts, as before.
    expect(activity.savedDuration({ ...turn, agent_review: review() })).toBe(32500);
    // A turn that does not say when its answer stood.
    expect(activity.savedDuration({ ...turn, agent_answer_fixed_at: undefined })).toBe(32500);
    app.dom.window.close();
  });
});
