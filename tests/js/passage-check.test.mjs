import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
<div id="threadAsk" class="thread-ask" hidden>
  <div class="thread-ask-text" id="threadAskText"></div>
  <div id="threadAskAttachments" hidden></div>
  <button type="button" class="thread-ask-more">Show full question</button>
</div>
`;

const PASTED = "Heat pumps work in old buildings below 55 degrees.\n\n- You always need **underfloor heating** for that.\n- The state pays up to 70 percent.";
const QUESTION = "Is this right?\n\n" + PASTED;

function claim(sentence, { agree = [], dissent = [], coverage } = {}) {
  const start = PASTED.indexOf(sentence);
  return { anchor: sentence, start, end: start + sentence.length, agree,
    dissent: dissent.map(model => ({ model, quote: `${model} says otherwise` })),
    coverage: coverage || (dissent.length ? "split" : agree.length >= 2 ? "supported" : "thin") };
}

function review(overrides = {}) {
  return { status: "succeeded", comparisons: [{ id: "c1" }], passage_check: {
    status: "succeeded", comparison_id: "c1", text: PASTED, answer_to: "Do heat pumps make sense in old buildings?",
    models_compared: ["Claude", "GPT", "Gemini"], issues: [],
    claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT", "Gemini"] }),
      claim("You always need **underfloor heating** for that.", { agree: ["Gemini"], dissent: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude"] })
    ], ...overrides } };
}

function boot() {
  const popover = vi.fn();
  const env = loadScripts(["static/js/app-core.js", "static/js/passage-check.js"], {
    body: BODY,
    before: window => {
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {},
        addListener() {}, removeListener() {} });
      window.App = { claimPopover: { open: popover } };
    }
  });
  const { window, document } = env;
  window.App.claimPopover = { open: popover };
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const wrap = document.getElementById("threadAsk");
  const text = document.getElementById("threadAskText");
  return { window, document, wrap, text, popover };
}

describe("passage check on the user's message", () => {
  it("marks every checked sentence with its verdict and keeps the user's own words", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());

    expect(wrap.classList.contains("has-passage-check")).toBe(true);
    const marks = [...text.querySelectorAll(".pc-claim")];
    expect(marks.map(mark => mark.dataset.verdict)).toEqual(["holds", "disputed", "unconfirmed"]);
    expect(marks.map(mark => mark.classList.contains("cx-claim"))).toEqual([true, true, true]);
    expect(marks[1].classList.contains("is-major")).toBe(true);
    // Pasted Markdown reads as text: no asterisks, bullets become dots.
    expect(marks[1].textContent).toBe("You always need underfloor heating for that.");
    expect(text.textContent).toContain("• You always need");
    expect(text.textContent.startsWith("Is this right?\n")).toBe(true);
    // A button's name replaces its text, so the sentence is part of it.
    expect(marks[1].getAttribute("aria-label"))
      .toBe("“You always need underfloor heating for that.” – 2 of 3 models disagree. Show details");
    expect(marks[2].getAttribute("aria-label")).toContain("Only one model says this. Show details");
    // The plain question is remembered apart from the marked DOM.
    expect(text.dataset.question).toBe(QUESTION.replace(/\s+/g, " ").trim());
  });

  it("sums the verdicts under the message and names the question it was checked against", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    const summary = wrap.querySelector(".passage-check");
    expect(summary.dataset.state).toBe("done");
    expect([...summary.querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 disputed", "1 unconfirmed", "1 holds"]);
    // The counts lead; a narrow line never starts with a separator.
    expect(summary.querySelector(".passage-check-head").textContent).toBe("1 disputed · 1 unconfirmed · 1 holds");
    expect([...summary.querySelectorAll(".passage-check-unit")].map(unit => unit.textContent))
      .toEqual(["1 disputed", "· 1 unconfirmed", "· 1 holds"]);
    expect(summary.querySelector(".passage-check-note").textContent).toBe(
      "Checked against 3 models as an answer to “Do heat pumps make sense in old buildings?”. "
      + "The models answered without seeing your text.");
  });

  it("opens the claim card for a sentence and for a count", () => {
    const { window, wrap, text, popover } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    text.querySelectorAll(".pc-claim")[1].click();
    expect(popover).toHaveBeenCalledTimes(1);
    const [card, anchor, models] = popover.mock.calls[0];
    expect(card.dissent.map(item => item.model)).toEqual(["Claude", "GPT"]);
    expect(anchor.dataset.verdict).toBe("disputed");
    expect(models).toEqual(["Claude", "GPT", "Gemini"]);

    wrap.querySelector('.passage-check-count[data-verdict="unconfirmed"]').click();
    expect(popover).toHaveBeenCalledTimes(2);
    expect(popover.mock.calls[1][1].dataset.verdict).toBe("unconfirmed");
    expect(wrap.classList.contains("is-open")).toBe(true);

    const enter = new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true });
    text.querySelector(".pc-claim").dispatchEvent(enter);
    expect(popover).toHaveBeenCalledTimes(3);
  });

  it("says it is checking while the run is live and admits an unfinished check afterwards", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    const waiting = review({ status: "waiting", claims: undefined, models_compared: undefined });
    window.App.passageCheck.apply(wrap, text, QUESTION, waiting, { live: true });
    expect(wrap.querySelector(".passage-check").textContent).toContain("Checking your text against independent answers");
    expect(text.querySelector(".pc-claim")).toBeNull();

    window.App.passageCheck.apply(wrap, text, QUESTION, waiting, { live: false });
    expect(wrap.querySelector(".passage-check").textContent).toBe("The check of your text did not finish.");
  });

  it("does not redraw a finished check when the run ends", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    const done = review();
    window.App.passageCheck.apply(wrap, text, QUESTION, done, { live: true });
    const first = text.querySelector(".pc-claim");
    window.App.passageCheck.apply(wrap, text, QUESTION, done, { live: false });
    expect(text.querySelector(".pc-claim")).toBe(first);
  });

  it("marks the right characters after an emoji (server offsets count code points)", () => {
    const { window, wrap, text } = boot();
    const pasted = "🚀 Paris is the capital of France. 📌 Berlin is the capital of Germany.";
    const points = Array.from(pasted);
    const span = sentence => {
      const start = points.join("").indexOf(sentence);
      const startPoint = Array.from(pasted.slice(0, start)).length;
      return { start: startPoint, end: startPoint + Array.from(sentence).length };
    };
    const question = "Check: " + pasted;
    window.App.setThreadQuestion(question);
    window.App.passageCheck.apply(wrap, text, question, { passage_check: {
      status: "succeeded", text: pasted, answer_to: "Capitals?", models_compared: ["A", "B"], issues: [],
      claims: [{ anchor: "x", ...span("Paris is the capital of France."), agree: ["A", "B"], dissent: [] },
               { anchor: "y", ...span("Berlin is the capital of Germany."), agree: ["A", "B"], dissent: [] }] } });
    expect([...text.querySelectorAll(".pc-claim")].map(mark => mark.textContent))
      .toEqual(["Paris is the capital of France.", "Berlin is the capital of Germany."]);
    expect(text.textContent).toContain("📌 Berlin");
  });

  it("does not open the card while text is being selected", () => {
    const { window, wrap, text, popover } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    const mark = text.querySelector(".pc-claim");
    window.getSelection().selectAllChildren(mark);
    mark.click();
    expect(popover).not.toHaveBeenCalled();
    window.getSelection().removeAllRanges();
    mark.click();
    expect(popover).toHaveBeenCalledTimes(1);
  });

  it("explains a failed check plainly", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION,
      review({ status: "failed", claims: undefined, issues: [{ code: "insufficient_answers" }] }));
    expect(wrap.querySelector(".passage-check").textContent)
      .toBe("Your text could not be checked: too few models answered.");
    expect(wrap.classList.contains("has-passage-check")).toBe(false);
  });

  it("survives a re-render of the same question and leaves a new question plain", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    window.App.setThreadQuestion(QUESTION);
    expect(text.querySelectorAll(".pc-claim")).toHaveLength(3);

    window.App.setThreadQuestion("A different question");
    expect(text.querySelector(".pc-claim")).toBeNull();
    expect(text.textContent).toBe("A different question");
    expect(wrap.querySelector(".passage-check")).toBeNull();
  });

  it("drops the marks when the turn has no check, and ignores malformed offsets", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    window.App.passageCheck.apply(wrap, text, QUESTION, { status: "succeeded", comparisons: [] });
    expect(text.querySelector(".pc-claim")).toBeNull();
    expect(text.textContent).toBe(QUESTION.replace(/\s+/g, " ").trim());

    const broken = review();
    broken.passage_check.claims.push({ anchor: "x", start: 5, end: 9999, agree: [], dissent: [] });
    broken.passage_check.claims.push({ anchor: "y", start: 2, end: 6, agree: [], dissent: [] });
    window.App.passageCheck.apply(wrap, text, QUESTION, broken);
    expect(text.querySelectorAll(".pc-claim")).toHaveLength(3);
  });

  it("shows the summary without marks when the message no longer contains the passage", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion("Shortened bookmark title");
    window.App.passageCheck.apply(wrap, text, "Shortened bookmark title", review());
    expect(text.querySelector(".pc-claim")).toBeNull();
    expect(text.textContent).toBe("Shortened bookmark title");
    expect(wrap.querySelector(".passage-check").textContent).toContain("Checked against 3 models as an answer to");
    // Nothing to jump to: the counts are text, not controls.
    expect(wrap.querySelector(".passage-check-count").tagName).toBe("SPAN");
  });
});
