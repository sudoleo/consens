import { describe, expect, it, vi } from "vitest";
import { marked } from "marked";
import DOMPurify from "dompurify";

import { loadScripts } from "./helpers/appWindow.mjs";

// The hover card of a marked sentence (consensus-insights.js): where it opens,
// on which devices, and on which marks (Apple audit follow-up, 2026-10-21).
const MOUSE = "(hover: hover) and (pointer: fine)";
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

function boot({ mode = "all", mouse = true } = {}) {
  const env = loadScripts([
    "static/js/user-settings.js", "static/js/sources.js", "static/js/markdown-stream.js",
    "static/js/consensus-anchor.js", "static/js/consensus-insights.js",
    "static/js/agent-review.js", "static/js/passage-check.js"
  ], {
    body: `
      <section id="agentAnswer"><div id="agentAnswerBody" class="consensus-answer-body"></div></section>
      <div id="consensusClaimsFallback" class="consensus-claims-fallback" hidden></div>
      <div id="claimPopover" hidden></div>
      <div id="claimSheetBackdrop" hidden></div>`,
    before(window) {
      if (mode === "none") window.localStorage.setItem("consensio.showConsensusMarkers.v1", "false");
      else window.localStorage.setItem("consensio.consensusHighlightMode.v1", mode);
      window.marked = marked;
      window.DOMPurify = DOMPurify(window);
      window.App = { answerReader: { openContext: vi.fn(), refreshContext: vi.fn() } };
      window.matchMedia = query => ({ matches: mouse && query === MOUSE, media: query,
        addEventListener() {}, removeEventListener() {} });
      // jsdom lays nothing out: a span in the document has one box, a
      // detached one none, as in a browser.
      window.HTMLElement.prototype.getClientRects = function () {
        return this.isConnected ? [{ width: 10, height: 10 }] : [];
      };
    }
  });
  const { window, document } = env;
  const body = document.getElementById("agentAnswerBody");
  const shown = () => document.querySelector(".insight-preview:not([hidden])");
  const hover = el => el.dispatchEvent(new window.MouseEvent("mouseenter"));
  const leave = el => el.dispatchEvent(new window.MouseEvent("mouseleave"));
  return { ...env, body, shown, hover, leave };
}

function review(text, data) {
  return { status: "succeeded", answer_version: 1, answer_hash: "h", versions: [{ id: 1, text, hash: "h" }],
    comparisons: [{ id: "c1", basis_hash: "b", question: "Which plan?", status: "succeeded", answers: [] }],
    checks: [{ comparison_id: "c1", basis_hash: "b", answer_hash: "h", status: "succeeded",
      differences_data: { models_compared: ["OpenAI", "Gemini"], differences: [], ...data } }] };
}

describe("where the hover card opens", () => {
  it("keeps a mark out of a link that becomes a source pill, so the card stays at its sentence", async () => {
    const { window, body, shown, hover, dom } = boot();
    // The disputed sentence ends inside the link: its last span sat in the
    // link's label, which the pill drops, and the card opened top left. (A
    // claim's badge behind the span kept the label from reading as the host.)
    const text = "The plan includes five seats, see [example.com](https://example.com/)\n\nAnother paragraph.";
    body.dataset.markdown = text;
    window.injectMarkdown(body, text, []);
    window.App.agentReview.render(body, review(text, { claims: [], differences: [{
      claim: "the seats", consensus_anchor: "The plan includes five seats, see example.com", type: "contradiction",
      severity: "major", positions: [{ models: ["OpenAI"], stance: "Five", quote: "five" },
        { models: ["Gemini"], stance: "Three", quote: "three" }] }] }));
    expect(body.querySelector("a.src-ref")).not.toBeNull();
    expect(body.querySelector(".src-ref .cx-claim, a .cx-claim")).toBeNull();
    const mark = body.querySelector(".cx-claim");
    expect(mark.textContent).toBe("The plan includes five seats, see ");
    expect(mark.cxGroup.spans.every(span => span.isConnected)).toBe(true);
    hover(mark);
    await wait(160);
    expect([...shown().querySelectorAll(".cx-card-claim")].map(el => el.textContent)).toEqual(["Five", "Three"]);
    dom.window.close();
  });

  it("shows no card for a mark that left the page, and none left over from a redrawn text", async () => {
    const { window, document, body, shown, hover, dom } = boot();
    body.innerHTML = "<p>The tower is 330 metres tall.</p>";
    const data = { models_compared: ["OpenAI", "Gemini"], differences: [],
      claims: [{ anchor: "The tower is 330 metres tall.", agree: ["OpenAI", "Gemini"], dissent: [] }] };
    window.renderStoredConsensusClaims(body, data, document.createElement("div"), []);
    const stale = body.querySelector(".cx-claim");
    body.innerHTML = "<p>The tower is 330 metres tall.</p>";
    hover(stale);
    await wait(160);
    expect(shown()).toBeNull();
    // A card on screen goes when its text is marked anew.
    window.renderStoredConsensusClaims(body, data, document.createElement("div"), []);
    hover(body.querySelector(".cx-claim"));
    await wait(160);
    expect(shown()).not.toBeNull();
    window.renderStoredConsensusClaims(body, data, document.createElement("div"), []);
    expect(shown()).toBeNull();
    dom.window.close();
  });
});

describe("where the card stands beside its sentence", () => {
  // Max 2026-10-23: a disputed sentence split by **bold** into three spans,
  // its first word at the end of a line. The card took the first span for
  // the disputed words: it stood above the sentence, over the paragraph
  // before, and hung out of the text to the right, with room to spare below.
  const SENTENCE = "Die vollständigen Gewichte sollen bis 4. November erscheinen; bis dahin ist es offen.";
  const data = { models_compared: ["OpenAI", "Gemini"], claims: [], differences: [{
    claim: "Availability of the weights", consensus_anchor: SENTENCE, type: "contradiction", severity: "major",
    positions: [{ models: ["OpenAI"], stance: "Not yet", quote: "not yet", in_answer: true },
      { models: ["Gemini"], stance: "Already open", quote: "open" }] }] };
  const box = (left, top, width, height) => ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top });
  // [left, top, width] of each line of each span, as the browser laid them out.
  const LINES = { "Die": [[1152, 324, 26], [570, 353, 437]], "4.": [[1007, 353, 151]], " er": [[1158, 353, 97], [570, 382, 621]] };

  function laidOut(floorTop) {
    const env = boot();
    const { window, document, body } = env;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1917 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 910 });
    window.HTMLElement.prototype.getClientRects = function () {
      if (!this.isConnected) return [];
      if (this.classList.contains("cx-claim")) {
        const key = Object.keys(LINES).find(start => this.textContent.startsWith(start));
        return LINES[key].map(([left, top, width]) => box(left, top, width, 23));
      }
      return [box(0, 0, 10, 10)];
    };
    window.HTMLElement.prototype.getBoundingClientRect = function () {
      if (this.tagName === "P") return box(570, 324, 704, 81);
      if (this.classList.contains("chat-input-container")) return box(0, floorTop, 1917, 120);
      return box(0, 0, 0, 0);
    };
    for (const side of ["offsetWidth", "offsetHeight"]) {
      Object.defineProperty(window.HTMLElement.prototype, side, { configurable: true, get() {
        return this.classList.contains("insight-preview") ? (side === "offsetWidth" ? 344 : 300) : 0;
      } });
    }
    const composer = document.createElement("div");
    composer.className = "chat-input-container";
    document.body.appendChild(composer);
    body.innerHTML = "<p>Für den Alltag zählt das. Die vollständigen Gewichte sollen bis <strong>4. November</strong> erscheinen; bis dahin ist es offen.</p>";
    window.renderStoredConsensusClaims(body, data, document.createElement("div"), [], { focusDifference() {} });
    expect(body.querySelectorAll(".cx-claim")).toHaveLength(3);
    return env;
  }

  it("stands under the whole sentence where there is room, from the start of its last line", async () => {
    const env = laidOut(820);
    env.hover(env.body.querySelectorAll(".cx-claim")[1]);
    await wait(160);
    const card = env.shown();
    expect(card.dataset.placement).toBe("below");
    expect([card.style.left, card.style.top]).toEqual(["570px", "417px"]);
    expect(card.style.getPropertyValue("--cx-arrow-x")).toBe("28px");
    env.dom.window.close();
  });

  it("stands above it without room below, inside the text, the arrow on the word at the line's end", async () => {
    const env = laidOut(600);
    env.hover(env.body.querySelector(".cx-claim"));
    await wait(160);
    const card = env.shown();
    expect(card.dataset.placement).toBe("above");
    // The paragraph ends at 1274: the card's right edge stays there.
    expect([card.style.left, card.style.top]).toEqual(["930px", "12px"]);
    expect(card.style.getPropertyValue("--cx-arrow-x")).toBe("235px");
    env.dom.window.close();
  });
});

describe("reaching the card with the pointer", () => {
  const launch = { claim: "the launch date", consensus_anchor: "The launch is on Monday.", type: "contradiction",
    severity: "major", positions: [{ models: ["OpenAI"], stance: "Monday", quote: "Monday", in_answer: true },
      { models: ["Gemini"], stance: "Friday", quote: "Friday" }] };
  const tickets = { claim: "the ticket price", consensus_anchor: "Tickets cost ten euros.", type: "contradiction",
    severity: "major", positions: [{ models: ["OpenAI"], stance: "Ten", quote: "ten", in_answer: true },
      { models: ["Gemini"], stance: "Twelve", quote: "twelve" }] };
  function marked(env, differences, ways) {
    env.body.innerHTML = "<p>The launch is on Monday. Tickets cost ten euros.</p>";
    env.window.renderStoredConsensusClaims(env.body, { models_compared: ["OpenAI", "Gemini"], claims: [], differences },
      env.document.createElement("div"), [], ways);
    return [...env.body.querySelectorAll(".cx-claim")];
  }
  const sides = card => [...card.querySelectorAll(".cx-card-claim")].map(el => el.textContent);

  it("keeps it while the pointer is in it, and its footer leads into the reader", async () => {
    const env = boot();
    const ways = { focusDifference: vi.fn(), answerNavigation: { canOpen: () => true, open: vi.fn() } };
    const [mark] = marked(env, [launch], ways);
    env.hover(mark);
    await wait(160);
    const card = env.shown();
    // On its way into the card the pointer leaves the sentence: the card waits.
    env.leave(mark);
    env.hover(card);
    await wait(320);
    expect(env.shown()).toBe(card);
    expect(mark.classList.contains("is-hovered")).toBe(true);
    // The answer toolbar's ways, for the pointer only: the keyboard finds
    // them in the pinned card.
    const actions = [...card.querySelectorAll(".cx-card-action")];
    expect(actions.map(action => action.textContent)).toEqual(["Contradictions", "Answers"]);
    expect(actions.every(action => action.tabIndex === -1)).toBe(true);
    actions[1].click();
    // The answer of the other side, at its quote.
    expect(ways.answerNavigation.open).toHaveBeenCalledWith("Gemini", "Friday");
    expect(env.shown()).toBeNull();
    // The reader hands the focus back to the mark, not to a closed card.
    expect(env.document.activeElement).toBe(mark);
    env.hover(mark);
    await wait(160);
    env.shown().querySelector('.cx-card-action[data-section="differences"]').click();
    expect(ways.focusDifference).toHaveBeenCalledWith(0);
    env.dom.window.close();
  });

  it("goes a moment after the pointer left sentence and card", async () => {
    const env = boot();
    const [mark] = marked(env, [launch], { focusDifference() {} });
    env.hover(mark);
    await wait(160);
    const card = env.shown();
    env.leave(mark);
    env.hover(card);
    env.leave(card);
    expect(env.shown()).toBe(card);
    await wait(320);
    expect(env.shown()).toBeNull();
    expect(mark.classList.contains("is-hovered")).toBe(false);
    env.dom.window.close();
  });

  it("takes the sentence's highlight along when a click elsewhere ends the wait", async () => {
    const env = boot();
    const [mark] = marked(env, [launch], { focusDifference() {} });
    env.hover(mark);
    await wait(160);
    env.leave(mark);
    env.document.body.dispatchEvent(new env.window.MouseEvent("click", { bubbles: true }));
    expect(env.shown()).toBeNull();
    expect(mark.classList.contains("is-hovered")).toBe(false);
    env.dom.window.close();
  });

  it("is not taken over by a mark the pointer crosses on its way into it", async () => {
    const env = boot();
    const [launchMark, ticketMark] = marked(env, [launch, tickets], { focusDifference() {} });
    env.hover(launchMark);
    await wait(160);
    const card = env.shown();
    env.leave(launchMark);
    env.hover(ticketMark);
    env.leave(ticketMark);
    env.hover(card);
    await wait(200);
    expect(sides(env.shown())).toEqual(["Monday", "Friday"]);
    // Resting on the other mark brings its card.
    env.leave(card);
    env.hover(ticketMark);
    await wait(160);
    expect(sides(env.shown())).toEqual(["Ten", "Twelve"]);
    expect(launchMark.classList.contains("is-hovered")).toBe(false);
    env.dom.window.close();
  });
});

describe("which devices get the card", () => {
  const contradiction = {
    models_compared: ["OpenAI", "Gemini"], claims: [],
    differences: [{ claim: "the launch date", consensus_anchor: "The launch is on Monday.", type: "contradiction",
      severity: "major", positions: [{ models: ["OpenAI"], stance: "Monday", quote: "Monday" },
        { models: ["Gemini"], stance: "Friday", quote: "Friday" }] }]
  };
  function marked(env) {
    env.body.innerHTML = "<p>The launch is on Monday.</p>";
    env.window.renderStoredConsensusClaims(env.body, contradiction, env.document.createElement("div"), [],
      { focusDifference() {} });
    return env.body.querySelector(".cx-claim");
  }

  it("shows it for keyboard focus, not for a tap or a focus given back by a closed sheet", async () => {
    const env = boot();
    const mark = marked(env);
    expect(mark.getAttribute("tabindex")).toBe("0");
    // The reader closes and hands the focus back (model-answer-reader.js).
    env.document.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Escape" }));
    mark.focus();
    await wait(160);
    expect(env.shown()).toBeNull();
    mark.blur();
    // A tap focuses the sentence too.
    mark.dispatchEvent(new env.window.Event("pointerdown", { bubbles: true }));
    mark.focus();
    await wait(160);
    expect(env.shown()).toBeNull();
    mark.blur();
    // Tab to it: the preview, as for the pointer.
    env.document.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Tab" }));
    mark.focus();
    await wait(160);
    expect(env.shown().querySelector(".cx-card-vs").textContent).toBe("vs");
    env.dom.window.close();
  });

  it("never shows it on a touch phone", async () => {
    const env = boot({ mouse: false });
    const mark = marked(env);
    env.hover(mark);
    env.document.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Tab" }));
    mark.focus();
    await wait(160);
    expect(env.shown()).toBeNull();
    env.dom.window.close();
  });

  it("does not bring it back on a scroll once there is no pointer any more", async () => {
    const env = boot();
    const mark = marked(env);
    env.document.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Tab" }));
    mark.focus();
    await wait(160);
    expect(env.shown()).not.toBeNull();
    // The mouse is gone (a tablet without its keyboard case): a scroll hides
    // the card and, without a pointer, does not resume it.
    env.window.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    env.window.dispatchEvent(new env.window.Event("scroll"));
    await wait(160);
    expect(env.shown()).toBeNull();
    env.dom.window.close();
  });
});

describe("the checked sentences of the user's text", () => {
  const PASTED = "Heat pumps work below 55 degrees. You always need underfloor heating for that.";
  function check(sentence, agree, dissent) {
    const start = PASTED.indexOf(sentence);
    return { anchor: sentence, start, end: start + sentence.length, agree,
      dissent: dissent.map(model => ({ model, quote: `${model} says otherwise` })),
      coverage: dissent.length ? "split" : "supported" };
  }
  const passage = { status: "succeeded", passage_check: { status: "succeeded", comparison_id: "c1", text: PASTED,
    answer_to: "Heat pumps?", models_compared: ["Claude", "GPT", "Gemini"], issues: [], claims: [
      check("Heat pumps work below 55 degrees.", ["Claude", "GPT", "Gemini"], []),
      check("You always need underfloor heating for that.", ["Gemini"], ["Claude", "GPT"])] } };

  it("preview like an answer sentence; a click swaps it for the card, and closing the card brings none back", async () => {
    const env = boot({ mode: "concerns" });
    const { window, document, shown, hover, leave } = env;
    window.App.passageCheck.apply(env.body, passage);
    const quoted = document.querySelector(".passage-check-quote .pc-claim");
    hover(quoted);
    await wait(160);
    // The user's sentence against what the other models say.
    expect([...shown().querySelectorAll(".cx-card-claim")].map(el => el.textContent))
      .toEqual(["You always need underfloor heating for that.", "Claude says otherwise", "GPT says otherwise"]);
    expect(shown().querySelector(".cx-card-tag").textContent).toBe("In your text");
    quoted.click();
    expect(shown()).toBeNull();
    const popover = document.getElementById("claimPopover");
    expect(popover.hidden).toBe(false);
    // While the card is open, no second card comes up beside it.
    leave(quoted);
    hover(quoted);
    await wait(160);
    expect(shown()).toBeNull();
    // Escape closes the card and gives the focus back to the sentence.
    document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape" }));
    expect(popover.hidden).toBe(true);
    expect(document.activeElement).toBe(quoted);
    await wait(160);
    expect(shown()).toBeNull();
    env.dom.window.close();
  });

  it("previews nothing on a sentence the Highlights setting leaves unpainted", async () => {
    const env = boot({ mode: "concerns" });
    env.window.App.passageCheck.apply(env.body, passage);
    env.document.querySelector(".passage-check-toggle").click();
    const holds = env.document.querySelector('.passage-check-text .pc-claim[data-verdict="holds"]');
    expect(holds.classList.contains("is-quiet")).toBe(true);
    env.hover(holds);
    await wait(160);
    expect(env.shown()).toBeNull();
    env.dom.window.close();
  });
});

describe("provisional marks", () => {
  const data = { models_compared: ["OpenAI", "Gemini"], differences: [], claims: [
    { anchor: "The tower is tall.", agree: ["OpenAI", "Gemini"], dissent: [], coverage: "supported" },
    { anchor: "Tickets cost twenty euros.", agree: ["OpenAI"], coverage: "split",
      dissent: [{ model: "Gemini", quote: "Thirty euros", target: "twenty euros" }] },
    { anchor: "The queue is short.", agree: ["OpenAI"], dissent: [], coverage: "thin" },
    { anchor: "Not in the answer.", agree: ["OpenAI", "Gemini"], dissent: [], coverage: "supported" }] };

  it("mark every compared sentence alike, under every setting, without a verdict", async () => {
    const env = boot({ mode: "concerns" });
    const { window, document, body, shown, hover } = env;
    body.innerHTML = "<p>The tower is tall. Tickets cost twenty euros. The queue is short.</p>";
    const fallback = document.createElement("div");
    fallback.hidden = true;
    window.renderStoredConsensusClaims(body, data, fallback, [], { provisional: true });
    const marks = [...body.querySelectorAll(".cx-claim")];
    expect(marks.map(mark => mark.className)).toEqual(Array(3).fill("cx-claim is-provisional"));
    // No colour, count, disputed words or list: nothing says how it came out.
    expect(body.querySelector(".claim-badge, .cx-spot")).toBeNull();
    expect(fallback.hidden).toBe(true);
    hover(marks[1]);
    await wait(160);
    expect(shown().textContent).toBe("Compared with 2 model answersThe result appears once the whole answer is checked");
    // Nothing to open yet.
    marks[1].click();
    expect(document.getElementById("claimPopover").hidden).toBe(true);
    expect(marks[1].hasAttribute("tabindex")).toBe(false);
    env.dom.window.close();
  });

  it("are hidden with all highlights", async () => {
    const env = boot({ mode: "none" });
    env.body.innerHTML = "<p>The tower is tall.</p>";
    env.window.renderStoredConsensusClaims(env.body, data, env.document.createElement("div"), [], { provisional: true });
    expect(env.document.body.classList.contains("consensus-markers-hidden")).toBe(true);
    env.hover(env.body.querySelector(".cx-claim"));
    await wait(160);
    expect(env.shown()).toBeNull();
    env.dom.window.close();
  });
});
