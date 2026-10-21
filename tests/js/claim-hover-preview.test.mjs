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
    expect(shown().textContent).toContain("Contradiction");
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
    expect(env.shown().textContent).toContain("Contradiction");
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
    expect(shown().textContent).toContain("1/3");
    expect(shown().textContent).toContain("Click for the full breakdown");
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
