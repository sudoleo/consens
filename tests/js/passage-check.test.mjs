import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
<div id="threadAsk" class="thread-ask">
  <div class="thread-ask-text" id="threadAskText">Is this right?</div>
</div>
<section id="agentAnswer">
  <div id="agentAnswerActivity"></div>
  <div id="agentAnswerBody" class="consensus-answer-body"><p>Mostly, but not the underfloor heating.</p></div>
</section>
`;

const PASTED = "Heat pumps work in old buildings below 55 degrees.\n\n- You always need **underfloor heating** for that.\n- The state pays up to 70 percent.";
const NOTE = "Checked against 3 models as an answer to “Do heat pumps make sense in old buildings?” "
  + "The models answered without seeing your text.";

function claim(sentence, { agree = [], dissent = [], coverage, text = PASTED } = {}) {
  const start = text.indexOf(sentence);
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
  const env = loadScripts(["static/js/passage-check.js"], {
    body: BODY,
    before: window => {
      window.App = { claimPopover: { open: popover } };
      if (mode) window.document.body.dataset.consensusHighlightMode = mode;
    }
  });
  const { window, document } = env;
  window.App.claimPopover = { open: popover };
  window.App.answerReader = { openContext };
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const body = document.getElementById("agentAnswerBody");
  const card = () => document.querySelector(".passage-check");
  return { window, document, body, card, popover, openContext };
}

describe("result card of a checked pasted text", () => {
  it("sits right above the answer and leaves the user's message as it was sent", () => {
    const { window, document, body, card } = boot();
    const message = document.getElementById("threadAsk").outerHTML;
    window.App.passageCheck.apply(body, review());
    expect(card().nextElementSibling).toBe(body);
    expect(card().previousElementSibling.id).toBe("agentAnswerActivity");
    expect(card().getAttribute("aria-label")).toBe("Check of your text");
    expect(document.getElementById("threadAsk").outerHTML).toBe(message);
    expect(body.textContent).toBe("Mostly, but not the underfloor heating.");
    // A row put between them later does not separate card and answer.
    const row = document.createElement("div");
    body.before(row);
    window.App.passageCheck.apply(body, review());
    expect(card().nextElementSibling).toBe(body);
  });

  it("quotes only the sentences models disagree with, folding the rest in reading order", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    const rows = [...card().querySelector(".passage-check-quotes").children];
    expect(rows.map(row => row.className)).toEqual(["passage-check-fold", "passage-check-quote", "passage-check-fold"]);
    // A fold says what it holds.
    expect(rows[0].textContent).toBe("1 sentence holds");
    expect(rows[0].getAttribute("aria-label")).toBe("1 sentence holds: show the full text");
    expect(rows[2].textContent).toBe("1 unconfirmed sentence");
    const mark = rows[1].querySelector(".pc-claim");
    // Pasted Markdown reads as text, and a quoted list item has no bullet.
    expect(mark.textContent).toBe("You always need underfloor heating for that.");
    expect(mark.dataset.verdict).toBe("disputed");
    expect(mark.classList.contains("is-major")).toBe(true);
    expect(mark.classList.contains("is-quiet")).toBe(false);
    expect(rows[1].querySelector(".passage-check-verdict").textContent).toBe("2 of 3 models disagree");
    // A button's name replaces its text, so the sentence is part of it.
    expect(mark.getAttribute("aria-label"))
      .toBe("“You always need underfloor heating for that.” – 2 of 3 models disagree. Show details");
    expect(mark.getAttribute("role")).toBe("button");
    expect(mark.getAttribute("aria-haspopup")).toBe("dialog");
  });

  it("leads with the counts and names the question it was checked against", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    expect(card().dataset.state).toBe("done");
    expect(card().querySelector(".passage-check-eyebrow").textContent).toBe("Your text");
    expect([...card().querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 disputed", "1 unconfirmed", "1 holds"]);
    // The verdict colour sits on the number only.
    expect([...card().querySelectorAll(".passage-check-num")].map(num => num.textContent)).toEqual(["1", "1", "1"]);
    // Each count carries its separator, so a wrapped line never starts with a dot.
    expect([...card().querySelectorAll(".passage-check-unit")].map(unit => unit.textContent))
      .toEqual(["1 disputed ·", "1 unconfirmed ·", "1 holds"]);
    // No second full stop after a quoted question mark.
    expect(card().querySelector(".passage-check-note").textContent).toBe(NOTE);
    expect(card().querySelector(".passage-check-toggle").textContent).toBe("Show full text");
    expect(card().querySelector(".passage-check-toggle").getAttribute("aria-expanded")).toBe("false");
  });

  it("unfolds the whole text with every sentence marked, painted as the Highlights setting paints", async () => {
    const { window, document, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    card().querySelector(".passage-check-toggle").click();
    expect(card().classList.contains("is-full")).toBe(true);
    const text = card().querySelector(".passage-check-text");
    const marks = [...text.querySelectorAll(".pc-claim")];
    expect(marks.map(mark => mark.dataset.verdict)).toEqual(["holds", "disputed", "unconfirmed"]);
    expect(text.textContent).toContain("• You always need underfloor heating");
    // Default ("concerns"): only red and amber; the rest stays a working sentence.
    expect(marks.map(mark => mark.classList.contains("is-quiet"))).toEqual([true, false, true]);
    expect(marks[0].getAttribute("role")).toBe("button");
    const toggle = card().querySelector(".passage-check-toggle");
    expect(toggle.textContent).toBe("Show less");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(toggle);
    document.body.dataset.consensusHighlightMode = "all";
    await new Promise(resolve => setTimeout(resolve, 0));
    expect([...text.querySelectorAll(".pc-claim")].map(mark => mark.classList.contains("is-quiet")))
      .toEqual([false, false, false]);
    toggle.click();
    expect(card().querySelector(".passage-check-text")).toBeNull();
    expect(card().querySelectorAll(".passage-check-quote")).toHaveLength(1);
    // A fold unfolds as well.
    card().querySelector(".passage-check-fold").click();
    expect(card().querySelectorAll(".passage-check-text .pc-claim")).toHaveLength(3);
  });

  it("opens the claim card for a sentence, a count and the keyboard", () => {
    const { window, body, card, popover } = boot();
    window.App.passageCheck.apply(body, review());
    card().querySelector(".pc-claim").click();
    expect(popover).toHaveBeenCalledTimes(1);
    const [details, anchor, models] = popover.mock.calls[0];
    expect(details.dissent.map(item => item.model)).toEqual(["Claude", "GPT"]);
    expect(anchor.dataset.verdict).toBe("disputed");
    expect(models).toEqual(["Claude", "GPT", "Gemini"]);

    // A count of sentences the card does not quote unfolds the text first.
    card().querySelector('.passage-check-count[data-verdict="unconfirmed"]').click();
    expect(popover).toHaveBeenCalledTimes(2);
    expect(popover.mock.calls[1][1].dataset.verdict).toBe("unconfirmed");
    expect(popover.mock.calls[1][1].closest(".passage-check-text")).not.toBeNull();
    expect(card().classList.contains("is-full")).toBe(true);

    const enter = new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true });
    card().querySelector(".pc-claim").dispatchEvent(enter);
    expect(popover).toHaveBeenCalledTimes(3);
  });

  it("opens the model's answer from the claim card even while the run is still live", () => {
    const { window, body, card, popover, openContext } = boot();
    window.App.passageCheck.apply(body, review(), { live: true });
    card().querySelector(".pc-claim").click();
    const navigation = popover.mock.calls[0][3];
    expect(navigation.canOpen("Claude")).toBe(true);
    expect(navigation.canOpen("Mistral")).toBe(false);
    navigation.open("Claude", "Radiators work.");
    expect(openContext).toHaveBeenCalledTimes(1);
    const [context, options] = openContext.mock.calls[0];
    expect(context.answers[0].text).toBe("Radiators work.");
    expect(options).toMatchObject({ section: "answers", model: "Claude", quote: "Radiators work." });
  });

  it("says what runs while the models answer, then turns into the result", () => {
    const { window, body, card } = boot();
    const waiting = review({ status: "waiting", claims: undefined, models_compared: undefined });
    window.App.passageCheck.apply(body, waiting, { live: true });
    expect(card().dataset.state).toBe("running");
    expect(card().querySelector(".passage-check-status").textContent).toBe("Checking against independent answers…");
    expect(card().querySelector(".passage-check-note").textContent).toBe(
      "Checking it as an answer to “Do heat pumps make sense in old buildings?” The models answer without seeing your text.");
    expect(card().querySelector(".passage-check-toggle")).toBeNull();
    window.App.passageCheck.apply(body, review({ status: "running", claims: undefined }), { live: true });
    expect(card().querySelector(".passage-check-status").textContent).toBe("Checking each sentence…");
    window.App.passageCheck.apply(body, review(), { live: true });
    expect(card().dataset.state).toBe("done");
    expect(card().querySelectorAll(".passage-check-quote")).toHaveLength(1);

    // A run that ended without the check says so.
    window.App.passageCheck.apply(body, waiting, { live: false });
    expect(card().dataset.state).toBe("failed");
    expect(card().textContent).toBe("Your text" + "The check of your text did not finish.");
  });

  it("does not redraw a finished check when the run ends or the saved turn comes back reordered", () => {
    const { window, body, card } = boot();
    const done = review();
    window.App.passageCheck.apply(body, done, { live: true });
    const first = card().querySelector(".pc-claim");
    window.App.passageCheck.apply(body, done, { live: false });
    window.App.passageCheck.apply(body, reordered(done), { live: false });
    expect(card().querySelector(".pc-claim")).toBe(first);
  });

  it("keeps the unfolded text open when the run ends", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review(), { live: true });
    card().querySelector(".passage-check-toggle").click();
    window.App.passageCheck.apply(body, review({ issues: [{ code: "models_unavailable", count: 1 }] }), { live: false });
    expect(card().querySelectorAll(".passage-check-text .pc-claim")).toHaveLength(3);
    expect(card().querySelector(".passage-check-toggle").textContent).toBe("Show less");
    expect(card().querySelector(".passage-check-note").textContent).toBe(NOTE + " 1 model did not answer.");
  });

  it("marks the right characters after an emoji (server offsets count code points)", () => {
    const { window, body, card } = boot();
    const pasted = "\u{1F680} Paris is the capital of France. \u{1F4CC} Berlin is the capital of Germany.";
    const span = sentence => {
      const start = Array.from(pasted.slice(0, pasted.indexOf(sentence))).length;
      return { start, end: start + Array.from(sentence).length };
    };
    window.App.passageCheck.apply(body, { passage_check: {
      status: "succeeded", text: pasted, answer_to: "Capitals?", models_compared: ["A", "B"], issues: [],
      claims: [{ anchor: "x", ...span("Paris is the capital of France."), agree: ["A"], dissent: [{ model: "B" }] },
               { anchor: "y", ...span("Berlin is the capital of Germany."), agree: ["A", "B"], dissent: [] }] } });
    expect(card().querySelector(".passage-check-quote .pc-claim").textContent).toBe("Paris is the capital of France.");
    card().querySelector(".passage-check-toggle").click();
    expect([...card().querySelectorAll(".passage-check-text .pc-claim")].map(mark => mark.textContent))
      .toEqual(["Paris is the capital of France.", "Berlin is the capital of Germany."]);
    expect(card().querySelector(".passage-check-text").textContent).toContain("\u{1F4CC} Berlin");
  });

  it("shows a pasted table as text and keeps underscores", () => {
    const { window, body, card } = boot();
    const pasted = "| Type | Cost |\n|---|---|\n| Air source | 12000 euros |\nCall __init__ first, it is required.";
    window.App.passageCheck.apply(body, review({ text: pasted,
      claims: [claim("Call __init__ first, it is required.", { agree: ["A", "B"], text: pasted })] }));
    card().querySelector(".passage-check-toggle").click();
    const text = card().querySelector(".passage-check-text").textContent;
    expect(text).toContain("Type · Cost\n");
    expect(text).toContain("Air source · 12000 euros");
    expect(text).not.toContain("---");
    expect(text).toContain("__init__");
  });

  it("folds a text no model disagrees with into one row, and says when nothing could be checked", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review({ claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude"] })] }));
    expect(card().querySelector(".passage-check-quote")).toBeNull();
    expect([...card().querySelectorAll(".passage-check-fold")].map(row => row.textContent))
      .toEqual(["2 more sentences, 1 unconfirmed"]);
    expect(card().querySelector(".passage-check-toggle")).not.toBeNull();
    window.App.passageCheck.apply(body, review({ claims: [] }));
    expect(card().querySelector(".passage-check-status").textContent).toBe("No checkable statements found in your text.");
    expect(card().querySelector(".passage-check-body")).toBeNull();
    expect(card().querySelector(".passage-check-count")).toBeNull();
    expect(card().querySelector(".passage-check-toggle")).toBeNull();
  });

  it("quotes at most eight sentences and folds the rest", () => {
    const { window, body, card } = boot();
    const sentences = Array.from({ length: 12 }, (_, index) => `Claim number ${index + 1} is wrong.`);
    const text = sentences.join(" ");
    window.App.passageCheck.apply(body, review({ text,
      claims: sentences.map(sentence => claim(sentence, { agree: [], dissent: ["A", "B"], text })) }));
    const rows = [...card().querySelector(".passage-check-quotes").children];
    expect(rows.filter(row => row.matches(".passage-check-quote"))).toHaveLength(8);
    expect(rows.at(-1).textContent).toBe("4 disputed sentences");
  });

  it("does not open the claim card while text is being selected", () => {
    const { window, body, card, popover } = boot();
    window.App.passageCheck.apply(body, review());
    const mark = card().querySelector(".pc-claim");
    window.getSelection().selectAllChildren(mark);
    mark.click();
    expect(popover).not.toHaveBeenCalled();
    window.getSelection().removeAllRanges();
    mark.click();
    expect(popover).toHaveBeenCalledTimes(1);
  });

  it("explains a failed check plainly", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review({ status: "failed", claims: undefined, issues: [{ code: "insufficient_answers" }] }));
    expect(card().querySelector(".passage-check-status").textContent)
      .toBe("Your text could not be checked: too few models answered.");
    expect(card().querySelector(".pc-claim")).toBeNull();
    expect(card().querySelector(".passage-check-foot")).toBeNull();
    window.App.passageCheck.apply(body, review({ status: "failed", claims: undefined, issues: [{ code: "no_time" }] }));
    expect(card().querySelector(".passage-check-status").textContent)
      .toBe("Your text could not be checked: the answer needed the remaining time.");
    window.App.passageCheck.apply(body, review({ status: "cancelled", claims: undefined }));
    expect(card().querySelector(".passage-check-status").textContent).toBe("The check of your text was stopped.");
  });

  it("removes the card when the turn has no check, and ignores malformed offsets", () => {
    const { window, document, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    window.App.passageCheck.apply(body, { status: "succeeded", comparisons: [] });
    expect(card()).toBeNull();
    window.App.passageCheck.apply(body, review());
    window.App.passageCheck.apply(body, null);
    expect(card()).toBeNull();

    const broken = review();
    broken.passage_check.claims.push({ anchor: "x", start: 5, end: 9999, agree: [], dissent: [] });
    broken.passage_check.claims.push({ anchor: "y", start: 2, end: 6, agree: [], dissent: [] });
    window.App.passageCheck.apply(body, broken);
    expect(card().querySelector(".passage-check-counts").textContent).toBe("1 disputed · 1 unconfirmed · 1 holds");
    expect(document.querySelectorAll(".passage-check")).toHaveLength(1);
  });
});
