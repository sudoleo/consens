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
const NOTE = "Checked against 3 models that answered “Do heat pumps make sense in old buildings?” "
  + "without seeing your text.";

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

  it("quotes only the sentences models disagree with, with what a model says instead", () => {
    const { window, body, card, popover } = boot();
    window.App.passageCheck.apply(body, review());
    // No grey rows between the quotes: only the disputed sentence.
    const rows = [...card().querySelector(".passage-check-quotes").children];
    expect(rows.map(row => row.className)).toEqual(["passage-check-quote"]);
    const mark = rows[0].querySelector(".pc-claim");
    // Pasted Markdown reads as text, and a quoted list item has no bullet.
    expect(mark.textContent).toBe("You always need underfloor heating for that.");
    expect(mark.dataset.verdict).toBe("disputed");
    expect(mark.classList.contains("is-major")).toBe(true);
    expect(mark.classList.contains("is-quiet")).toBe(false);
    const line = rows[0].querySelector(".passage-check-verdict");
    expect(line.textContent).toBe("2 of 3 models disagree – Claude: “Claude says otherwise”");
    expect(line.querySelector(".passage-check-who").textContent).toBe("2 of 3 models disagree");
    // A button's name replaces its text, so the sentence is part of it; the
    // verdict line right below says the rest.
    expect(mark.getAttribute("aria-label")).toBe("“You always need underfloor heating for that.” – Show details");
    expect(mark.getAttribute("role")).toBe("button");
    expect(mark.getAttribute("aria-haspopup")).toBe("dialog");
    // The verdict line opens the same card as the sentence.
    line.click();
    expect(popover).toHaveBeenCalledTimes(1);
    expect(popover.mock.calls[0][1]).toBe(mark);
  });

  it("says a single dissenting model disagrees, and shortens a long quote", () => {
    const { window, body, card } = boot();
    const long = "Radiators are fine in most cases ".repeat(10).trim() + ".";
    const data = review();
    data.passage_check.claims[1] = { ...data.passage_check.claims[1], agree: ["Gemini", "GPT"],
      dissent: [{ model: "Claude", quote: "" }, { model: "Mistral", quote: `**${long}**` }] };
    window.App.passageCheck.apply(body, data);
    const line = card().querySelector(".passage-check-verdict");
    expect(line.querySelector(".passage-check-who").textContent).toBe("2 of 4 models disagree");
    const quote = line.querySelector(".passage-check-instead").textContent;
    // The first model with words, without Markdown, cut at a word.
    expect(quote.startsWith("Mistral: “Radiators are fine")).toBe(true);
    expect(quote.endsWith("…”")).toBe(true);
    expect(quote.length).toBeLessThan(200);
    data.passage_check.claims[1] = { ...data.passage_check.claims[1], agree: ["Gemini", "GPT"],
      dissent: [{ model: "Claude", quote: "" }] };
    window.App.passageCheck.apply(body, data);
    expect(card().querySelector(".passage-check-verdict").textContent).toBe("1 of 3 models disagrees");
  });

  it("leads with the result as one sentence, a strip of the sentences and a legend", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    expect(card().dataset.state).toBe("done");
    // No uppercase label: the headline is the result, its number in the verdict colour.
    expect(card().querySelector(".passage-check-eyebrow")).toBeNull();
    const headline = card().querySelector(".passage-check-headline");
    expect(headline.textContent).toBe("Models disagree with 1 of 3 statements in your text");
    expect(headline.querySelector(".passage-check-figure").className).toBe("passage-check-figure is-disputed");
    // Runs of one verdict in reading order; decoration, the legend says it in words.
    const strip = card().querySelector(".passage-check-strip");
    expect(strip.getAttribute("aria-hidden")).toBe("true");
    expect([...strip.children].map(segment => segment.dataset.verdict)).toEqual(["holds", "disputed", "unconfirmed"]);
    expect([...card().querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 disputed", "1 unconfirmed", "1 holds"]);
    expect([...card().querySelectorAll(".passage-check-num")].map(num => num.textContent)).toEqual(["1", "1", "1"]);
    // The way to the full text sits at the end of the legend.
    expect(card().querySelector(".passage-check-legend").lastElementChild.className).toBe("passage-check-toggle");
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
    expect(card().querySelector(".passage-check-status").textContent).toBe("Checking your text against independent answers…");
    expect(card().querySelector(".passage-check-note").textContent).toBe(
      "Checking it as an answer to “Do heat pumps make sense in old buildings?” The models answer without seeing your text.");
    expect(card().querySelector(".passage-check-toggle")).toBeNull();
    expect(card().querySelector(".passage-check-legend")).toBeNull();
    window.App.passageCheck.apply(body, review({ status: "running", claims: undefined }), { live: true });
    expect(card().querySelector(".passage-check-status").textContent).toBe("Checking each sentence of your text…");
    window.App.passageCheck.apply(body, review(), { live: true });
    expect(card().dataset.state).toBe("done");
    expect(card().querySelectorAll(".passage-check-quote")).toHaveLength(1);

    // A run that ended without the check says so.
    window.App.passageCheck.apply(body, waiting, { live: false });
    expect(card().dataset.state).toBe("failed");
    expect(card().textContent).toBe("The check of your text did not finish.");
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

  it("keeps table cells apart when every cell is its own sentence", () => {
    const { window, body, card } = boot();
    const pasted = "| Type | Cost |\n|---|---|\n| Air source pump | 12000 euros total |\n| Ground source pump | 20000 euros total |";
    const cells = ["Air source pump", "12000 euros total", "Ground source pump", "20000 euros total"];
    window.App.passageCheck.apply(body, review({ text: pasted,
      claims: cells.map(cell => claim(cell, { agree: ["A", "B"], text: pasted })) }));
    card().querySelector(".passage-check-toggle").click();
    const text = card().querySelector(".passage-check-text").textContent;
    expect(text).toBe("Type · Cost\nAir source pump · 12000 euros total\nGround source pump · 20000 euros total");
  });

  it("reads pasted Markdown as text: links, italics, code, quotes and fences", () => {
    const { window, body, card } = boot();
    const pasted = "> Note: see [the docs](https://x.io/a) for *more* details.\n\n```python\nrun(`x`)\n```\n"
      + "Use `pip install` and ***always*** pin 2 * 3 versions.";
    window.App.passageCheck.apply(body, review({ text: pasted,
      claims: [claim("Use `pip install` and ***always*** pin 2 * 3 versions.", { agree: ["A"], dissent: ["B"], text: pasted })] }));
    expect(card().querySelector(".passage-check-quote .pc-claim").textContent).toBe("Use pip install and always pin 2 * 3 versions.");
    card().querySelector(".passage-check-toggle").click();
    const text = card().querySelector(".passage-check-text").textContent;
    expect(text).toContain("Note: see the docs for more details.");
    expect(text).toContain("run(x)");
    expect(text).not.toMatch(/```|\]\(|^>/m);
  });

  it("drops a claim that overlaps one already kept", () => {
    const { window, body, card } = boot();
    const pasted = "Alpha beta gamma. Delta epsilon zeta. Eta theta.";
    const at = (from, to) => ({ start: from, end: to, agree: ["A", "B"], dissent: [] });
    window.App.passageCheck.apply(body, { passage_check: { status: "succeeded", text: pasted, models_compared: ["A", "B"],
      issues: [], claims: [at(0, 37), at(6, 10), at(18, 48)] } });
    card().querySelector(".passage-check-toggle").click();
    expect(card().querySelector(".passage-check-text").textContent).toBe(pasted);
    expect(card().querySelectorAll(".passage-check-text .pc-claim")).toHaveLength(1);
  });

  it("folds the card again when it shows another turn's text", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review());
    card().querySelector(".passage-check-toggle").click();
    expect(card().classList.contains("is-full")).toBe(true);
    const other = "Paris is the capital of Spain.";
    window.App.passageCheck.apply(body, review({ text: other, comparison_id: "c2",
      claims: [claim(other, { dissent: ["A", "B"], text: other })] }));
    expect(card().classList.contains("is-full")).toBe(false);
    expect(card().querySelector(".passage-check-quote .pc-claim").textContent).toBe(other);
  });

  it("sums up a text no model disagrees with in its headline, and says when nothing could be checked", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review({ claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude"] })] }));
    expect(card().querySelector(".passage-check-quote")).toBeNull();
    // Nothing contradicted is not "fine": it says how much is confirmed.
    expect(card().querySelector(".passage-check-headline").textContent)
      .toBe("No model contradicts your text; 1 of 2 statements is confirmed");
    expect([...card().querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 unconfirmed", "1 holds"]);
    // No empty rail: the headline says it all.
    expect(card().querySelector(".passage-check-body").hidden).toBe(true);
    card().querySelector(".passage-check-toggle").click();
    expect(card().querySelector(".passage-check-body").hidden).toBe(false);
    window.App.passageCheck.apply(body, review({ claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude", "GPT"] })] }));
    const headline = card().querySelector(".passage-check-headline");
    expect(headline.textContent).toBe("All 2 statements in your text hold up");
    expect(headline.querySelector(".passage-check-figure").className).toBe("passage-check-figure is-holds");
    // A single verdict is the headline already: no legend counts repeat it.
    expect(card().querySelector(".passage-check-count")).toBeNull();
    expect(card().querySelector(".passage-check-toggle")).not.toBeNull();
    window.App.passageCheck.apply(body, review({ text: "The state pays.", claims: [
      claim("The state pays.", { agree: ["Claude", "GPT"], text: "The state pays." })] }));
    expect(card().querySelector(".passage-check-headline").textContent).toBe("The statement in your text holds up");
    window.App.passageCheck.apply(body, review({ claims: [] }));
    expect(card().querySelector(".passage-check-status").textContent).toBe("No sentence of your text could be checked against the answers.");
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
    expect(card().querySelectorAll(".passage-check-quote")).toHaveLength(8);
    // The headline counts all of them; the full text shows the rest.
    expect(card().querySelector(".passage-check-headline").textContent).toBe("Models disagree with 12 of 12 statements in your text");
    // The four not quoted are one click away.
    const more = card().querySelector(".passage-check-more");
    expect(more.textContent).toBe("4 more in the full text");
    more.click();
    expect(card().classList.contains("is-full")).toBe(true);
    expect(card().querySelectorAll(".passage-check-text .pc-claim")).toHaveLength(12);
    // One run of one verdict is one segment.
    expect(card().querySelectorAll(".passage-check-strip i")).toHaveLength(1);
    expect(card().querySelector(".passage-check-strip i").style.flexGrow).toBe("12");
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
    expect([...card().querySelectorAll(".passage-check-count")].map(chip => chip.textContent))
      .toEqual(["1 disputed", "1 unconfirmed", "1 holds"]);
    expect(document.querySelectorAll(".passage-check")).toHaveLength(1);
  });

  it("never calls an unconfirmed or partly checked text fine", () => {
    const { window, body, card } = boot();
    const headline = () => card().querySelector(".passage-check-headline").textContent;
    window.App.passageCheck.apply(body, review({ claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude"] }),
      claim("The state pays up to 70 percent.", { agree: [] })] }));
    expect(headline()).toBe("No model contradicts your text, but none of its 2 statements is confirmed");
    // A single verdict still shows no legend counts, and the toggle stands alone.
    expect(card().querySelector(".passage-check-counts")).toBeNull();
    expect(card().querySelector(".passage-check-legend").children).toHaveLength(1);
    window.App.passageCheck.apply(body, review({ text: "The state pays.",
      claims: [claim("The state pays.", { agree: ["Claude"], text: "The state pays." })] }));
    expect(headline()).toBe("No model contradicts the statement in your text, but none confirms it");
    // Sentences the check could not reach: the headline counts only the checked ones.
    window.App.passageCheck.apply(body, review({ issues: [{ code: "sentences_unchecked", count: 2 }], claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude", "GPT"] })] }));
    expect(headline()).toBe("All 2 checked statements in your text hold up");
    expect(card().querySelector(".passage-check-note").textContent).toContain("2 sentences could not be checked.");
  });

  it("names the toggle's target and words a single model's verdict right", () => {
    const { window, body, card } = boot();
    window.App.passageCheck.apply(body, review({ models_compared: ["Claude"], claims: [
      claim("You always need **underfloor heating** for that.", { dissent: ["Claude"] })] }));
    const toggle = card().querySelector(".passage-check-toggle");
    expect(toggle.getAttribute("aria-controls")).toBe(card().querySelector(".passage-check-body").id);
    expect(card().querySelector(".passage-check-who").textContent).toBe("1 of 1 model disagrees");
  });

  it("opens on the full text under All checks, and follows the setting until the reader chooses", async () => {
    const { window, document, body, card } = boot({ mode: "all" });
    const tick = () => new Promise(resolve => setTimeout(resolve, 0));
    window.App.passageCheck.apply(body, review({ claims: [
      claim("Heat pumps work in old buildings below 55 degrees.", { agree: ["Claude", "GPT"] }),
      claim("The state pays up to 70 percent.", { agree: ["Claude", "GPT"] })] }));
    // Every sentence holds: folded, there would be nothing highlighted at all.
    expect(card().classList.contains("is-full")).toBe(true);
    const marks = [...card().querySelectorAll(".passage-check-text .pc-claim")];
    expect(marks.map(mark => mark.classList.contains("is-quiet"))).toEqual([false, false]);
    expect(card().querySelector(".passage-check-toggle").textContent).toBe("Show less");
    document.body.dataset.consensusHighlightMode = "concerns";
    await tick();
    expect(card().classList.contains("is-full")).toBe(false);
    document.body.dataset.consensusHighlightMode = "all";
    await tick();
    expect(card().classList.contains("is-full")).toBe(true);
    // The reader folds it: the setting no longer moves it.
    card().querySelector(".passage-check-toggle").click();
    document.body.dataset.consensusHighlightMode = "concerns";
    await tick();
    document.body.dataset.consensusHighlightMode = "all";
    await tick();
    expect(card().classList.contains("is-full")).toBe(false);
  });
});
