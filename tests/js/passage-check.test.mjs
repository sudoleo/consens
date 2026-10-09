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
const NOTE = "Checked against 3 models as an answer to “Do heat pumps make sense in old buildings?” "
  + "The models answered without seeing your text.";

function claim(sentence, { agree = [], dissent = [], coverage } = {}) {
  const start = PASTED.indexOf(sentence);
  return { anchor: sentence, start, end: start + sentence.length, agree,
    dissent: dissent.map(model => ({ model, quote: `${model} says otherwise` })),
    coverage: coverage || (dissent.length ? "split" : agree.length >= 2 ? "supported" : "thin") };
}

function review(overrides = {}) {
  return { status: "succeeded",
    comparisons: [{ id: "c1", question: "Heat pumps?", answers: [
      { provider: "anthropic", provider_label: "Claude", model: { model: "claude", label: "Claude Haiku" }, text: "Radiators work." }] }],
    passage_check: {
      status: "succeeded", comparison_id: "c1", text: PASTED, answer_to: "Do heat pumps make sense in old buildings?",
      models_compared: ["Claude", "GPT", "Gemini"], issues: [],
      claims: [
        claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT", "Gemini"] }),
        claim("You always need **underfloor heating** for that.", { agree: ["Gemini"], dissent: ["Claude", "GPT"] }),
        claim("The state pays up to 70 percent.", { agree: ["Claude"] })
      ], ...overrides } };
}

// The same content as a saved turn returns it: Firestore keeps no key order.
function reordered(value) {
  if (Array.isArray(value)) return value.map(reordered);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().reverse().map(key => [key, reordered(value[key])]));
}

function boot({ mode } = {}) {
  const popover = vi.fn();
  const openContext = vi.fn();
  const env = loadScripts(["static/js/app-core.js", "static/js/passage-check.js"], {
    body: BODY,
    before: window => {
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {},
        addListener() {}, removeListener() {} });
      window.App = { claimPopover: { open: popover } };
      if (mode) window.document.body.dataset.consensusHighlightMode = mode;
    }
  });
  const { window, document } = env;
  window.App.claimPopover = { open: popover };
  window.App.answerReader = { openContext };
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const wrap = document.getElementById("threadAsk");
  const text = document.getElementById("threadAskText");
  return { window, document, wrap, text, popover, openContext };
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
    expect(text.textContent.startsWith("Is this right?\n\n")).toBe(true);
    // A button's name replaces its text, so the sentence is part of it.
    expect(marks[1].getAttribute("aria-label"))
      .toBe("“You always need underfloor heating for that.” – 2 of 3 models disagree. Show details");
    expect(marks[2].getAttribute("aria-label")).toContain("Only one model says this. Show details");
    expect(marks[1].getAttribute("aria-haspopup")).toBe("dialog");
    // The plain question is remembered apart from the marked DOM.
    expect(text.dataset.question).toBe(QUESTION.replace(/\s+/g, " ").trim());
  });

  it("paints what the Highlights setting paints; the rest stays a quiet, working sentence", () => {
    const { window, document, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    const quiet = () => [...text.querySelectorAll(".pc-claim")].map(mark => mark.classList.contains("is-quiet"));
    // Default ("concerns"): only red and amber.
    expect(quiet()).toEqual([true, false, true]);
    expect(text.querySelector(".pc-claim").getAttribute("role")).toBe("button");
    document.body.dataset.consensusHighlightMode = "all";
    return new Promise(resolve => setTimeout(resolve, 0)).then(() => {
      expect(quiet()).toEqual([false, false, false]);
    });
  });

  it("sums the verdicts under the message and names the question it was checked against", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    const summary = wrap.querySelector(".passage-check");
    expect(summary.dataset.state).toBe("done");
    expect([...summary.querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 disputed", "1 unconfirmed", "1 holds"]);
    // The counts lead; each carries its separator, so a wrapped line never
    // starts with a dot.
    expect(summary.querySelector(".passage-check-head").textContent).toBe("1 disputed · 1 unconfirmed · 1 holds");
    expect([...summary.querySelectorAll(".passage-check-unit")].map(unit => unit.textContent))
      .toEqual(["1 disputed ·", "1 unconfirmed ·", "1 holds"]);
    // No second full stop after a quoted question mark.
    expect(summary.querySelector(".passage-check-note").textContent).toBe(NOTE);
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

  it("opens the model's answer from the card even while the run is still live", () => {
    const { window, wrap, text, popover, openContext } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review(), { live: true });
    text.querySelectorAll(".pc-claim")[1].click();
    const navigation = popover.mock.calls[0][3];
    expect(navigation.canOpen("Claude")).toBe(true);
    expect(navigation.canOpen("Mistral")).toBe(false);
    navigation.open("Claude", "Radiators work.");
    expect(openContext).toHaveBeenCalledTimes(1);
    const [context, options] = openContext.mock.calls[0];
    expect(context.answers[0].text).toBe("Radiators work.");
    expect(options).toMatchObject({ section: "answers", model: "Claude", quote: "Radiators work." });
  });

  it("unfolds the message when Tab reaches a sentence below the fold", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    text.scrollTop = 40;
    text.querySelectorAll(".pc-claim")[2].focus();
    expect(wrap.classList.contains("is-open")).toBe(true);
    expect(text.scrollTop).toBe(0);
  });

  it("keeps the bubble's shape from the first frame: the passage keeps its lines while it is checked", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    const waiting = review({ status: "waiting", claims: undefined, models_compared: undefined });
    window.App.passageCheck.apply(wrap, text, QUESTION, waiting, { live: true });
    expect(wrap.classList.contains("has-passage-check")).toBe(true);
    expect(text.querySelector(".pc-claim")).toBeNull();
    const plain = text.textContent;
    const summary = wrap.querySelector(".passage-check");
    expect(summary.querySelector(".passage-check-head").textContent).toContain("Checking your text against independent answers");
    expect(summary.querySelector(".passage-check-note").textContent).toBe(
      "Checking it as an answer to “Do heat pumps make sense in old buildings?” The models answer without seeing your text.");
    expect(summary.children).toHaveLength(2);
    window.App.passageCheck.apply(wrap, text, QUESTION, review(), { live: true });
    expect(text.textContent).toBe(plain);
    expect(summary.children).toHaveLength(2);

    window.App.passageCheck.apply(wrap, text, QUESTION, waiting, { live: false });
    expect(wrap.querySelector(".passage-check").textContent).toBe("The check of your text did not finish.");
  });

  it("does not redraw a finished check when the run ends or the saved turn comes back reordered", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    const done = review();
    window.App.passageCheck.apply(wrap, text, QUESTION, done, { live: true });
    const first = text.querySelector(".pc-claim");
    const summary = wrap.querySelector(".passage-check-head");
    window.App.passageCheck.apply(wrap, text, QUESTION, done, { live: false });
    window.App.passageCheck.apply(wrap, text, QUESTION, reordered(done), { live: false });
    expect(text.querySelector(".pc-claim")).toBe(first);
    expect(wrap.querySelector(".passage-check-head")).toBe(summary);
  });

  it("marks the right characters after an emoji (server offsets count code points)", () => {
    const { window, wrap, text } = boot();
    const pasted = "\u{1F680} Paris is the capital of France. \u{1F4CC} Berlin is the capital of Germany.";
    const span = sentence => {
      const start = Array.from(pasted.slice(0, pasted.indexOf(sentence))).length;
      return { start, end: start + Array.from(sentence).length };
    };
    const question = "Check: " + pasted;
    window.App.setThreadQuestion(question);
    window.App.passageCheck.apply(wrap, text, question, { passage_check: {
      status: "succeeded", text: pasted, answer_to: "Capitals?", models_compared: ["A", "B"], issues: [],
      claims: [{ anchor: "x", ...span("Paris is the capital of France."), agree: ["A", "B"], dissent: [] },
               { anchor: "y", ...span("Berlin is the capital of Germany."), agree: ["A", "B"], dissent: [] }] } });
    expect([...text.querySelectorAll(".pc-claim")].map(mark => mark.textContent))
      .toEqual(["Paris is the capital of France.", "Berlin is the capital of Germany."]);
    expect(text.textContent).toContain("\u{1F4CC} Berlin");
  });

  it("shows a pasted table as text and keeps underscores", () => {
    const { window, wrap, text } = boot();
    const pasted = "| Type | Cost |\n|---|---|\n| Air source | 12000 euros |\nCall __init__ first, it is required.";
    const question = "Check: " + pasted;
    window.App.setThreadQuestion(question);
    window.App.passageCheck.apply(wrap, text, question, review({ text: pasted, claims: [] }));
    expect(text.textContent).toContain("Type · Cost\n");
    expect(text.textContent).toContain("Air source · 12000 euros");
    expect(text.textContent).not.toContain("---");
    expect(text.textContent).toContain("__init__");
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

  it("explains a failed check plainly and keeps the bubble's shape", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION,
      review({ status: "failed", claims: undefined, issues: [{ code: "insufficient_answers" }] }));
    expect(wrap.querySelector(".passage-check").textContent)
      .toBe("Your text could not be checked: too few models answered.");
    expect(text.querySelector(".pc-claim")).toBeNull();
    window.App.passageCheck.apply(wrap, text, QUESTION,
      review({ status: "failed", claims: undefined, issues: [{ code: "no_time" }] }));
    expect(wrap.querySelector(".passage-check").textContent)
      .toBe("Your text could not be checked: the answer needed the remaining time.");
  });

  it("survives a re-render of the same question and leaves a new or empty question plain", () => {
    const { window, wrap, text } = boot();
    window.App.setThreadQuestion(QUESTION);
    window.App.passageCheck.apply(wrap, text, QUESTION, review());
    window.App.setThreadQuestion(QUESTION);
    expect(text.querySelectorAll(".pc-claim")).toHaveLength(3);

    window.App.setThreadQuestion("A different question");
    expect(text.querySelector(".pc-claim")).toBeNull();
    expect(text.textContent).toBe("A different question");
    expect(wrap.querySelector(".passage-check")).toBeNull();

    window.App.passageCheck.apply(wrap, text, "A different question", review({ text: "A different question",
      claims: [{ anchor: "A different question", start: 0, end: 20, agree: ["A", "B"], dissent: [] }] }));
    window.App.setThreadQuestion("");
    expect(text.textContent).toBe("");
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

  it("opens a count's card at the count when the message does not show the passage", () => {
    const { window, wrap, text, popover } = boot();
    window.App.setThreadQuestion("Germany.");
    window.App.passageCheck.apply(wrap, text, "Germany.", review());
    expect(text.querySelector(".pc-claim")).toBeNull();
    expect(text.textContent).toBe("Germany.");
    const chip = wrap.querySelector('.passage-check-count[data-verdict="disputed"]');
    chip.click();
    expect(popover).toHaveBeenCalledTimes(1);
    expect(popover.mock.calls[0][1]).toBe(chip);
    expect(popover.mock.calls[0][0].dissent).toHaveLength(2);
  });
});
