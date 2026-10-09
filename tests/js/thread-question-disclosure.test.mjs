import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
<div id="threadAsk" class="thread-ask" hidden>
  <div class="thread-ask-bubble">
    <div class="thread-ask-text" id="threadAskText"></div>
    <button type="button" class="thread-ask-more">Show more</button>
  </div>
  <div id="threadAskAttachments" hidden></div>
</div>
<div id="threadPendingAsk" class="thread-ask" hidden>
  <div class="thread-ask-bubble">
    <div class="thread-ask-text" id="threadPendingAskText"></div>
    <button type="button" class="thread-ask-more">Show more</button>
  </div>
  <div id="threadPendingAskAttachments" hidden></div>
</div>
`;

function boot() {
  return loadScripts(["static/js/app-core.js", "static/js/composer-quote.js"], {
    body: BODY,
    before: window => {
      window.matchMedia = () => ({
        matches: false,
        addEventListener() {},
        removeEventListener() {},
        addListener() {},
        removeListener() {}
      });
    }
  });
}

describe("thread question disclosure", () => {
  it("stays open when a running context projects the same question again", () => {
    const { window, document } = boot();
    const question = "A long question that is projected again while its answers stream.";

    window.App.setThreadQuestion(question);
    const wrap = document.getElementById("threadAsk");
    const more = wrap.querySelector(".thread-ask-more");
    wrap.classList.add("is-long");
    more.click();

    expect(wrap.classList.contains("is-open")).toBe(true);
    expect(more.textContent).toBe("Show less");
    expect(more.getAttribute("aria-expanded")).toBe("true");

    // run-view.js does this repeatedly for the visible run while provider
    // deltas arrive. It must not be interpreted as a new question.
    window.App.setThreadQuestion(question);

    expect(wrap.classList.contains("is-open")).toBe(true);
    expect(wrap.classList.contains("is-long")).toBe(true);
    expect(more.textContent).toBe("Show less");
    expect(more.getAttribute("aria-expanded")).toBe("true");
  });

  it("resets the disclosure when the projected question actually changes", () => {
    const { window, document } = boot();
    const wrap = document.getElementById("threadAsk");
    const more = wrap.querySelector(".thread-ask-more");

    window.App.setThreadQuestion("First long question");
    wrap.classList.add("is-long");
    more.click();
    window.App.setThreadQuestion("Second long question");

    expect(wrap.classList.contains("is-open")).toBe(false);
    expect(wrap.classList.contains("is-long")).toBe(false);
    expect(more.textContent).toBe("Show more");
    expect(more.getAttribute("aria-expanded")).toBe("false");
  });

  it("keeps the paragraphs of a sent message and flattens only runs of spaces", () => {
    const { window, document } = boot();
    const [CR, NL, TAB] = [13, 10, 9].map(code => String.fromCharCode(code));

    window.App.setThreadQuestion(`First   paragraph. ${CR}${NL}${CR}${NL}${CR}${NL} Second${TAB}line${NL}third line`);

    const text = document.getElementById("threadAskText");
    // Paragraphs become blocks: a blank line would be one of the three lines
    // the folded bubble shows. Line breaks inside a paragraph stay (pre-wrap).
    const paragraphs = [...text.querySelectorAll(".thread-ask-paragraph")].map(node => node.textContent);
    expect(paragraphs).toEqual(["First paragraph.", `Second line${NL}third line`]);
    expect(text.dataset.question).toBe(`First paragraph.${NL}${NL}Second line${NL}third line`);

    window.App.setThreadQuestion(`One paragraph${NL}with a line break`);
    expect(text.querySelector(".thread-ask-paragraph")).toBeNull();
    expect(text.textContent).toBe(`One paragraph${NL}with a line break`);
  });

  it("shows an Ask-about-this quote as a block below the typed question", () => {
    const { window, document } = boot();
    const { typedMarker, quoteOnlyPrefix, close } = window.App.quote.format;

    window.App.setThreadQuestion(`How likely is 200?${typedMarker}Ageing: slowing is realistic.${close}`);

    const text = document.getElementById("threadAskText");
    const quote = text.querySelector(".thread-ask-quote");
    expect(quote.textContent).toBe("Ageing: slowing is realistic.");
    expect(text.textContent).toBe("How likely is 200?Ageing: slowing is realistic.");
    expect(text.textContent).not.toContain("Quoted from");
    // The full sent text stays the identity of the message.
    expect(text.dataset.question).toBe(`How likely is 200?${typedMarker}Ageing: slowing is realistic.${close}`);

    window.App.setThreadQuestion(`${quoteOnlyPrefix}A claim.${close}`);
    expect(text.textContent).toBe("A claim.");
    expect(text.querySelector(".thread-ask-quote").textContent).toBe("A claim.");
  });
});
