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
