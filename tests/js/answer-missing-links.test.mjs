/**
 * Links of an agent answer that lead nowhere (sources.js markMissingAnswerLinks,
 * the review's ``links`` from agent_answer_links.py).
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts(["static/js/sources.js"], {
    before(target) {
      target.App = { state: { set() {} }, t: (text, values = {}) => text.replace(/\{(\w+)\}/g, (_, key) => values[key]) };
    },
  });
}

function answer(window, html) {
  const body = window.document.createElement("div");
  body.innerHTML = html;
  window.document.body.append(body);
  return body;
}

const review = missing => ({ links: { checked: 3, missing } });

describe("links that lead nowhere", () => {
  it("strikes through exactly the listed links and says why", () => {
    const { window } = boot();
    const body = answer(window, '<p><a href="https://example.org/gone#part">Bericht</a> '
      + '<a href="https://EXAMPLE.org/fine">Fine</a> <a href="https://example.net/x">Other</a></p>');
    window.markMissingAnswerLinks(body, review([
      { url: "https://example.org/gone", status: 404, retrieved: false },
      { url: "https://example.net/x", status: 410, retrieved: true },
    ]));
    const [gone, fine, other] = body.querySelectorAll("a");
    expect(gone.classList.contains("answer-link-missing")).toBe(true);
    expect(gone.title).toContain("the site says there is no such page");
    expect(gone.getAttribute("aria-label")).toBe("Bericht, page not found");
    expect(gone.getAttribute("href")).toBe("https://example.org/gone#part");
    expect(fine.classList.contains("answer-link-missing")).toBe(false);
    expect(fine.hasAttribute("title")).toBe(false);
    expect(other.classList.contains("answer-link-missing")).toBe(true);
  });

  it("never marks a source pill and takes the mark back once the link is no longer listed", () => {
    const { window } = boot();
    const body = answer(window, '<a class="src-ref" href="https://example.org/gone">1</a> '
      + '<a href="https://example.org/gone">Gone</a>');
    window.markMissingAnswerLinks(body, review([{ url: "https://example.org/gone", status: 410 }]));
    const [pill, link] = body.querySelectorAll("a");
    expect(pill.classList.contains("answer-link-missing")).toBe(false);
    expect(link.classList.contains("answer-link-missing")).toBe(true);
    window.markMissingAnswerLinks(body, {});
    expect(link.classList.contains("answer-link-missing")).toBe(false);
    expect(link.hasAttribute("title") || link.hasAttribute("aria-label")).toBe(false);
  });
});
