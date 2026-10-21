import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// Review 2 (2026-10-21): main.py wraps a route's detail object as
// {error: {error, error_code, …}}. Consensus and Compare read only {detail},
// so an empty daily allowance said "You don’t have access to this." and the
// allowance card never came. Every form of a refusal reads the same; the
// agreed flat form {error: "<sentence>", code, retry_after} too.
const SENTENCE = "Today’s allowance doesn’t cover another run. It resets at 00:00 UTC.";
const FORMS = {
  wrapped: { error: { error: SENTENCE, error_code: "token_budget_exhausted", required_tokens: 9000, is_pro_user: false } },
  flat: { error: SENTENCE, code: "token_budget_exhausted", required_tokens: 9000 },
  detail: { detail: { error: SENTENCE, error_code: "token_budget_exhausted", required_tokens: 9000 } },
};

function boot() {
  return loadScripts(["static/js/usage-limit.js"], {
    body: `<section id="runBlocked" hidden><h2 id="runBlockedTitle"></h2><button id="runBlockedClose"></button>
      <p id="runBlockedBody"></p><p id="runBlockedMeta" hidden></p><div id="runBlockedActions"></div></section>
      <textarea id="questionInput"></textarea>`,
    before(window) {
      window.HTMLElement.prototype.scrollIntoView = () => {};
    },
  });
}

describe("a refused run in every form the server sends", () => {
  it.each(Object.entries(FORMS))("%s: is the day's allowance, with its sentence", (_form, body) => {
    const { window, document } = boot();
    const { App } = window;
    expect(App.usageLimit.isLimitError(body)).toBe(true);
    expect(App.userError(body)).toBe(SENTENCE);
    expect(App.userError(App.httpError({ status: 403 }, body))).toBe(SENTENCE);
    expect(App.errorFields(body).required_tokens).toBe(9000);
    App.usageLimit.show({ data: body, source: "run", phase: "prepare" });
    expect(document.getElementById("runBlocked").hidden).toBe(false);
    expect(document.getElementById("runBlockedTitle").textContent).toBe("Not enough of today’s allowance left");
    window.close();
  });

  it("never takes a short wait for the day's allowance", () => {
    const { window } = boot();
    const { App } = window;
    expect(App.usageLimit.isLimitError({ error: { error: "Too many requests.", code: "rate_limited", retry_after: 60 } })).toBe(false);
    expect(App.usageLimit.isLimitError({ error: "Too many requests.", code: "rate_limited", retry_after: 60 })).toBe(false);
    window.close();
  });
});
