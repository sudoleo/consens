import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * Copy under an Agent answer (answer-copy.js): the Markdown as text, the
 * rendered answer as HTML without the page's own controls, and a word that
 * says it copied without moving anything beside it.
 */
const MARKDOWN = "## Tickets\n\nA ticket costs **24 euros** [S1].\n\n![The arena](picture:p2)\n\n| Day | Open |\n| --- | --- |\n| Mon | 9:00 |";
const RENDERED = `<h2 id="h" class="md-heading">Tickets</h2>
  <p data-claim="c1"><span class="cx-claim is-audit is-major" role="button" tabindex="0" style="--cx-reveal-delay: 0ms">A ticket costs <strong>24 euros</strong></span>
    <a class="src-ref" href="https://colosseo.it/en/">colosseo.it</a><span class="src-ref-sep"></span>.</p>
  <div class="md-picture-line"><span class="md-picture" data-picture="p2"><figure class="agent-vm-picture"><img src="/agent/files/x" alt="The arena"><button>Remove</button></figure></span></div>
  <table class="md-shaped"><thead><tr><th align="left">Day</th><th>Open</th></tr></thead>
    <tbody><tr><td class="is-numeric">Mon<span class="md-bar" aria-hidden="true"><i></i></span></td><td colspan="1">9:00</td></tr></tbody></table>
  <div class="md-block-tools md-table-tools"><svg aria-hidden="true"></svg><button type="button" class="md-block-tool table-copy" data-word="CSV"></button></div>
  <ul class="md-task-list"><li class="md-task-item"><button type="button" class="md-task-box" role="checkbox" aria-checked="true"></button>Book</li></ul>
  <pre class="has-copy"><code class="language-python">print(1)</code><button type="button" class="code-copy" aria-label="Copy code"><svg></svg></button></pre>
  <p><a href="javascript:alert(1)">bad</a> <a href="https://example.org/a" target="_blank" rel="noopener">good</a></p>`;

function boot({ clipboard = "items", body = RENDERED, markdown = MARKDOWN } = {}) {
  const writes = [], texts = [], events = [];
  const app = loadScripts(["static/js/answer-copy.js"], {
    body: `<section class="agent-answer"><div id="answer" class="consensus-answer-body"></div>
      <section class="agent-review"><nav class="agent-evidence-links"><button class="agent-evidence-link">Sources</button></nav></section></section>`,
    before(window) {
      window.App = {
        toast: vi.fn(), trackAppEvent: vi.fn(),
        sourceRefs: { plainText: ref => ` (${ref.textContent})` },
      };
      if (clipboard === "items") {
        window.ClipboardItem = class { constructor(items) { this.items = items; } };
        Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: {
          write: vi.fn(async items => { writes.push(items); }), writeText: vi.fn(async text => { texts.push(text); }) } });
      } else if (clipboard === "event") {
        Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: undefined });
        window.document.execCommand = vi.fn(command => {
          if (command !== "copy") return false;
          const data = {};
          const event = new window.Event("copy", { cancelable: true });
          event.clipboardData = { setData: (type, value) => { data[type] = value; } };
          window.document.dispatchEvent(event);
          events.push(data);
          return event.defaultPrevented;
        });
      } else {
        Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: {
          writeText: vi.fn(async () => { throw new Error("denied"); }) } });
        window.document.execCommand = vi.fn(() => false);
      }
    },
  });
  const answer = app.document.getElementById("answer");
  answer.innerHTML = body;
  answer.dataset.markdown = markdown;
  answer._agentReview = app.document.querySelector(".agent-review");
  return { ...app, answer, writes, texts, events };
}

// jsdom's Blob has no text(): read it as a page would.
function blobText(window, blob) {
  return new Promise(resolve => {
    const reader = new window.FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsText(blob);
  });
}

describe("Copy under an Agent answer", () => {
  it("puts the Markdown as text and the rendered answer as HTML, without the page's controls", () => {
    const { window, answer } = boot();
    const { text, html } = window.App.answerCopy.payload(answer);
    // The places of the turn's pictures name nothing outside the page.
    expect(text).toBe("## Tickets\n\nA ticket costs **24 euros** [S1].\n\n| Day | Open |\n| --- | --- |\n| Mon | 9:00 |");
    const doc = new window.DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
    expect(doc.querySelector("h2").textContent).toBe("Tickets");
    expect(doc.querySelector("strong").textContent).toBe("24 euros");
    // A pill is its domains in brackets, never "colosseo.it" as a chip.
    expect(doc.querySelector("p").textContent.replace(/\s+/g, " ").trim()).toBe("A ticket costs 24 euros (colosseo.it).");
    expect(doc.querySelector("th").getAttribute("align")).toBe("left");
    expect(doc.querySelectorAll("td")[1].getAttribute("colspan")).toBe("1");
    expect(doc.querySelector("li").textContent).toBe("☑ Book");
    expect(doc.querySelector("pre").textContent).toBe("print(1)");
    // No picture of the workspace, no button, nothing hidden from readers,
    // no class, data or state of this page, no script address.
    expect(doc.querySelectorAll("img, button, svg, [aria-hidden], [class], [style], [role], [tabindex], [data-claim]")).toHaveLength(0);
    // The line under a table goes whole, not as an empty block after it.
    expect(doc.querySelector("table").nextElementSibling.tagName).toBe("UL");
    const links = [...doc.querySelectorAll("a")].map(a => [a.textContent, a.getAttribute("href"), a.attributes.length]);
    expect(links).toEqual([["bad", null, 0], ["good", "https://example.org/a", 1]]);
    // The answer on the page keeps everything.
    expect(answer.querySelector(".md-picture img")).not.toBeNull();
    expect(answer.querySelector(".src-ref")).not.toBeNull();
  });

  it("stands first among the answer's actions and copies both kinds in one go", async () => {
    vi.useFakeTimers();
    const { window, document, answer, writes } = boot();
    window.App.answerCopy.button(answer, { eligible: true });
    const pill = document.querySelector(".agent-copy-pill");
    expect(document.querySelector(".agent-evidence-links").nextElementSibling).toBe(pill);
    expect(pill.className).toBe("consensus-share-pill agent-copy-pill");
    expect(pill.getAttribute("aria-label")).toBe("Copy answer");
    // Both words stand in the cell from the start, the second unseen.
    expect([...pill.querySelectorAll(".agent-copy-word > span")].map(word => word.textContent)).toEqual(["Copy", "Copied"]);
    // Called again (every projection), it stays where it is.
    window.App.answerCopy.button(answer, { eligible: true });
    expect(document.querySelectorAll(".agent-copy-pill")).toHaveLength(1);

    pill.click();
    await vi.waitFor(() => expect(writes).toHaveLength(1));
    const item = writes[0][0].items;
    expect(Object.keys(item).sort()).toEqual(["text/html", "text/plain"]);
    expect([item["text/plain"].type, item["text/html"].type]).toEqual(["text/plain", "text/html"]);
    await vi.waitFor(() => expect(pill.classList.contains("is-copied")).toBe(true));
    expect(pill.getAttribute("aria-label")).toBe("Copied");
    expect(window.App.toast).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1700);
    expect(pill.classList.contains("is-copied")).toBe(false);
    expect(pill.getAttribute("aria-label")).toBe("Copy answer");
    vi.useRealTimers();
  });

  it("copies the answer that stands at the click, a correction's too", async () => {
    const { window, document, answer, writes } = boot();
    window.App.answerCopy.button(answer, { eligible: true });
    answer.dataset.markdown = "Corrected.";
    document.querySelector(".agent-copy-pill").click();
    await vi.waitFor(() => expect(writes).toHaveLength(1));
    expect(await blobText(window, writes[0][0].items["text/plain"])).toBe("Corrected.");
    expect(await blobText(window, writes[0][0].items["text/html"])).toContain("<h2>Tickets</h2>");
  });

  it("copies through a copy event where the browser takes no clipboard items", async () => {
    const { window, document, answer, events } = boot({ clipboard: "event" });
    window.App.answerCopy.button(answer, { eligible: true });
    document.querySelector(".agent-copy-pill").click();
    await vi.waitFor(() => expect(events).toHaveLength(1));
    expect(events[0]["text/plain"]).toContain("## Tickets");
    expect(events[0]["text/html"]).toContain("<table>");
    await vi.waitFor(() => expect(document.querySelector(".agent-copy-pill").classList.contains("is-copied")).toBe(true));
  });

  it("says it once when the browser refuses, and claims nothing", async () => {
    const { window, document, answer } = boot({ clipboard: "refused" });
    window.App.answerCopy.button(answer, { eligible: true });
    const pill = document.querySelector(".agent-copy-pill");
    pill.click();
    await vi.waitFor(() => expect(window.App.toast).toHaveBeenCalledWith({ message: "Copy to clipboard failed.", tone: "error" }));
    expect(pill.classList.contains("is-copied")).toBe(false);
  });

  it("opens the row Watch and Share stand in when the answer has no evidence row, and leaves with it", () => {
    const { window, document, answer } = boot();
    answer._agentReview.remove();
    answer._agentReview = null;
    window.App.answerCopy.button(answer, { eligible: true });
    const row = answer.nextElementSibling;
    expect(row.className).toBe("agent-watch-pill-row");
    expect(row.firstElementChild).toBe(document.querySelector(".agent-copy-pill"));
    window.App.answerCopy.button(answer, { eligible: false });
    expect(document.querySelector(".agent-copy-pill, .agent-watch-pill-row")).toBeNull();
  });
});
