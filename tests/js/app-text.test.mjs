import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// One locale for dates and numbers, one sentence per failure (Apple-Audit H1, H8, H9).
function boot({ online = true } = {}) {
  const { window } = loadScripts(["static/js/app-text.js"], {
    before(window) {
      Object.defineProperty(window.navigator, "onLine", { configurable: true, get: () => online });
    },
  });
  return window;
}

function response(status, body, headers = {}) {
  return new Response(body, { status, headers });
}

describe("App.format", () => {
  const now = new Date(2026, 9, 20, 15, 0).getTime();

  it("writes dates, times and numbers the same way in every browser locale", () => {
    const { App } = boot();
    const date = new Date(2026, 9, 19, 14, 3, 12);
    expect(App.format.date(date, { now })).toBe("Oct 19");
    expect(App.format.date(new Date(2025, 9, 19), { now })).toBe("Oct 19, 2025");
    expect(App.format.date(date, { year: true, now })).toBe("Oct 19, 2026");
    expect(App.format.date(new Date(2026, 9, 21), { weekday: true, now })).toBe("Wed, Oct 21");
    expect(App.format.time(new Date(2026, 9, 19, 2, 0))).toBe("02:00");
    expect(App.format.time(date)).toBe("14:03");
    expect(App.format.dateTime(date, { now })).toBe("Oct 19, 14:03");
    expect(App.format.number(48213)).toBe("48,213");
    expect(App.format.number(1.25, { digits: 1 })).toBe("1.3");
    expect(App.format.count(1, "source")).toBe("1 source");
    expect(App.format.count(3, "source")).toBe("3 sources");
    expect(App.format.date("not a date")).toBe("");
  });

  it("writes every span of time in one style", () => {
    const { App } = boot();
    expect(App.format.duration(23_400)).toBe("23s");
    expect(App.format.duration(187_000)).toBe("3m 7s");
    expect(App.format.duration(3_725_000)).toBe("1h 2m 5s");
    expect(App.format.duration(5 * 3_600_000 + 12 * 60_000, { minutes: true })).toBe("5h 12m");
    expect(App.format.duration(20_000, { minutes: true })).toBe("1m");
    expect(App.format.duration(2 * 3_600_000, { minutes: true })).toBe("2h");
  });

  it("says a time behind and a time ahead as a person does", () => {
    const { App } = boot();
    expect(App.format.relative(now - 20_000, now)).toBe("just now");
    expect(App.format.relative(now - 12 * 60_000, now)).toBe("12m ago");
    expect(App.format.relative(now - 3 * 3_600_000, now)).toBe("3h ago");
    expect(App.format.relative(new Date(2026, 9, 19, 9, 0), now)).toBe("yesterday");
    // Earlier the same day is never "yesterday" (review F, 2026-10-21).
    const lateEvening = new Date(2026, 9, 20, 23, 50).getTime();
    expect(App.format.relative(new Date(2026, 9, 20, 0, 10), lateEvening)).toBe("23h ago");
    expect(App.format.relative(new Date(2026, 9, 19, 23, 40), new Date(2026, 9, 20, 1, 0).getTime())).toBe("1h ago");
    expect(App.format.relative(new Date(2026, 9, 16, 9, 0), now)).toBe("4 days ago");
    expect(App.format.relative(new Date(2026, 9, 3, 9, 0), now)).toBe("on Oct 3");
    expect(App.format.upcoming(new Date(2026, 9, 20, 18, 30), now)).toBe("today, 18:30");
    expect(App.format.upcoming(new Date(2026, 9, 21, 9, 0), now)).toBe("tomorrow, 09:00");
    expect(App.format.upcoming(new Date(2026, 9, 23, 9, 0), now)).toBe("Friday, 09:00");
    expect(App.format.upcoming(new Date(2026, 9, 30, 9, 0), now)).toBe("Oct 30, 09:00");
  });
});

describe("App.userError", () => {
  it("never shows the engine's words for a request without an answer", () => {
    const offline = boot({ online: false });
    expect(offline.App.userError(new TypeError("Load failed"), { context: "send" }))
      .toBe("You’re offline. Your message is back in the box.");
    expect(offline.App.userError(new TypeError("Failed to fetch")))
      .toBe("You’re offline. Check your connection and try again.");

    const online = boot();
    expect(online.App.userError(new TypeError("Failed to fetch")))
      .toBe("consens.io can’t be reached right now. Try again in a moment.");
    expect(online.App.userError(new Error("Firebase: Error (auth/network-request-failed).")))
      .toBe("consens.io can’t be reached right now. Try again in a moment.");
    // What streamSSERequest rethrows keeps the engine's name and message.
    expect(online.App.userError(Object.assign(new Error("NetworkError when attempting to fetch resource."), { name: "TypeError" }), { context: "send" }))
      .toBe("consens.io can’t be reached right now. Your message is back in the box.");
  });

  it("words a body that is not JSON (a proxy page) as unreachable, never the parse error", async () => {
    const { App } = boot();
    expect(App.userError(new SyntaxError("The string did not match the expected pattern.")))
      .toBe("consens.io can’t be reached right now. Try again in a moment.");
    expect(App.userError(new SyntaxError("Unexpected token '<', \"<!DOCTYPE \"... is not valid JSON")))
      .toBe("consens.io can’t be reached right now. Try again in a moment.");
    const page = response(200, "<!doctype html><title>Proxy</title>", { "Content-Type": "text/html" });
    const failure = await App.readJson(page).catch(error => error);
    expect(failure.unreadable).toBe(true);
    expect(App.userError(failure)).toBe("consens.io can’t be reached right now. Try again in a moment.");
    // A refusal with an HTML body: the status speaks.
    expect(await App.readJson(response(502, "<html>Bad gateway</html>"))).toEqual({});
    expect(await App.readJson(response(200, ""))).toEqual({});
    expect(await App.readJson(response(200, '{"ok":true}'))).toEqual({ ok: true });
  });

  it("shows the server's sentence and its codes, and words bare statuses", async () => {
    const { App } = boot();
    const limited = App.httpError(response(429, "", { "Retry-After": "300" }),
      { error: "Too many requests in a short time. Please try again in 5 minutes.", code: "rate_limited", retry_after: 300 });
    expect(limited.status).toBe(429);
    expect(limited.code).toBe("rate_limited");
    expect(limited.retryAfter).toBe(300);
    expect(App.userError.kind(limited)).toBe("rate_limited");
    expect(App.userError(limited)).toBe("Too many requests in a short time. Please try again in 5 minutes.");
    // A 429 from somewhere else (no sentence): the same rule from Retry-After.
    expect(App.userError(App.httpError(response(429, "", { "Retry-After": "600" }), {})))
      .toBe("Too many requests in a short time. Try again in 10 minutes.");
    expect(App.userError(App.httpError(response(409, ""), { error: "You already watch this question.", code: "already_watched", watch_id: "w1" })))
      .toBe("You already watch this question.");
    expect(App.userError({ error: "You have reached today’s limit.", code: "limit_reached" })).toBe("You have reached today’s limit.");
    expect(App.userError({ detail: { error: "Delete a chat to make room." } })).toBe("Delete a chat to make room.");
    expect(App.userError(App.httpError(response(500, ""), {}))).toBe("Something went wrong on our side. Try again in a moment.");
    expect(App.userError(App.httpError(response(503, ""), {}))).toBe("consens.io can’t be reached right now. Try again in a moment.");
    expect(App.userError(App.httpError(response(401, ""), {}))).toBe("Your session has ended. Log in again.");
    expect(App.userError(App.httpError(response(404, ""), { detail: "Not Found" }))).toBe("This is no longer available.");
    expect(App.userError(new Error("Consensus HTTP 503"))).toBe("consens.io can’t be reached right now. Try again in a moment.");
    // FastAPI's validation list is no sentence.
    expect(App.userError(App.httpError(response(422, ""), { detail: [{ msg: "field required" }] }), { context: "save" }))
      .toBe("This couldn’t be saved. Try again.");
  });

  // Review 2 (2026-10-21): main.py wraps a route's detail object, so a
  // refusal arrives as {error: {error, error_code, …}}; the agreed flat form
  // {error: "<sentence>", code, retry_after} reads the same.
  it("reads a refusal whose error is an object as well as the flat form", () => {
    const { App } = boot();
    const sentence = "Today’s allowance doesn’t cover another run. It resets at 00:00 UTC.";
    const nested = { error: { error: sentence, error_code: "token_budget_exhausted", required_tokens: 9000,
      token_budget: { remaining: 10 } } };
    const refused = App.httpError(response(403, ""), nested);
    expect(refused.code).toBe("token_budget_exhausted");
    expect(refused.serverMessage).toBe(sentence);
    expect(App.userError(refused)).toBe(sentence);
    expect(App.userError(nested)).toBe(sentence);
    expect(App.errorFields(nested)).toMatchObject({ error: sentence, error_code: "token_budget_exhausted",
      required_tokens: 9000, token_budget: { remaining: 10 } });
    const flat = { error: sentence, code: "token_budget_exhausted", retry_after: 0 };
    expect(App.errorFields(flat)).toMatchObject({ error: sentence, code: "token_budget_exhausted" });
    expect(App.errorFields({ detail: { error: "Delete a chat to make room.", code: "bookmark_count_limit" } }))
      .toMatchObject({ error: "Delete a chat to make room.", code: "bookmark_count_limit" });
    expect(App.errorFields({ detail: { error: "x" } }).detail).toBeUndefined();
    expect(App.errorFields({ detail: "Not Found" })).toMatchObject({ error: "Not Found", detail: "Not Found" });
    expect(App.errorFields(null)).toEqual({});
    const wait = App.httpError(response(429, ""), { error: { error: "Wait a moment.", code: "rate_limited", retry_after: 120 } });
    expect(wait.retryAfter).toBe(120);
    expect(App.userError.kind(wait)).toBe("rate_limited");
  });

  // Review F: a 5xx label from the server's log ("Error updating watch") is
  // no sentence for a reader; a coded refusal or a real sentence still is.
  it("never shows a server error label as the sentence", () => {
    const { App } = boot();
    const ours = "Something went wrong on our side. Try again in a moment.";
    expect(App.userError(App.httpError(response(500, ""), { error: "Error updating watch" }), { context: "save" })).toBe(ours);
    expect(App.userError(App.httpError(response(500, ""), { error: "Chat storage error" }))).toBe(ours);
    expect(App.userError(App.httpError(response(503, ""), { detail: "Chat context unavailable" }))).toBe(ours);
    expect(App.userError(App.httpError(response(503, ""), { detail: "Could not start your chat. Please try again." })))
      .toBe("Could not start your chat. Please try again.");
    expect(App.userError(App.httpError(response(503, ""),
      { error: { error: "The allowance service is busy right now", error_code: "usage_storage_busy" } })))
      .toBe("The allowance service is busy right now");
    // A 4xx keeps its words as before.
    expect(App.userError(App.httpError(response(409, ""), { error: "You already watch this question", code: "already_watched" })))
      .toBe("You already watch this question");
  });

  it("keeps our own sentences, hides bugs and says nothing for a cancel", () => {
    const { App } = boot();
    expect(App.userError(new Error("This file is larger than 25 MB."))).toBe("This file is larger than 25 MB.");
    expect(App.userError(new TypeError("Cannot read properties of undefined (reading 'id')"), { context: "load" }))
      .toBe("This couldn’t be loaded. Try again.");
    expect(App.userError(new TypeError("x is not a function"), { fallback: "Sharing failed. Try again." }))
      .toBe("Sharing failed. Try again.");
    expect(App.userError(new DOMException("Request cancelled", "AbortError"))).toBe("");
    expect(App.userError(Object.assign(new Error("The connection is taking too long. Try again."), { name: "TimeoutError" }), { context: "send" }))
      .toBe("The connection is taking too long. Your message is back in the box.");
    expect(App.userError(null)).toBe("Something went wrong. Try again.");
    expect(App.userError("Failed to fetch")).toBe("consens.io can’t be reached right now. Try again in a moment.");
  });
});

describe("App.words", () => {
  it("has one word per state", () => {
    const { App } = boot();
    expect(App.words.check).toBe("Answer check");
    expect(App.words.failed).toBe("Failed");
    expect(App.words.stopped).toBe("Stopped");
    expect(Object.isFrozen(App.words)).toBe(true);
  });
});
