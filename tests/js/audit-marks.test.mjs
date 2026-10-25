/**
 * Audit instead of comparison (Agent, admins): the comparison models review
 * the finished answer and mark passages with notes (agent_audit.py). The page
 * shows them with the shared markers (renderStoredAuditMarks): wrong red,
 * doubtful amber, incomplete grey, the quoted words carrying the colour, the
 * notes in the mark's card. Unmarked text stays plain: no green, no counts.
 */
import { afterEach, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

let opened = [];
afterEach(() => {
  opened.forEach(dom => dom.window.close());
  opened = [];
});

function boot(html, mode = null) {
  const env = loadScripts(["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: `<select id="consensusHighlightsSelect">
        <option value="all">All checks</option><option value="contradictions">Contradictions only</option>
        <option value="concerns">Disagreements</option><option value="critical">Critical</option><option value="none">None</option>
      </select>
      <div id="consensusAnswerBody" class="consensus-answer-body">${html}</div>
      <div id="consensusClaimsFallback" class="consensus-claims-fallback" hidden></div>
      <div id="claimPopover" hidden></div><div id="claimSheetBackdrop" hidden></div>`,
    before(window) {
      if (mode) window.localStorage.setItem("consensio.consensusHighlightMode.v1", mode);
      window.App = window.App || {};
      window.App.consensusBodyEl = () => window.document.getElementById("consensusAnswerBody");
      window.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    }
  });
  opened.push(env.dom);
  env.window.Element.prototype.scrollIntoView = function () {};
  return env;
}

const ANSWER = "<p>The Eiffel Tower is 330 metres tall. It was built in 1889 for the World's Fair. "
  + "Tickets to the top cost 14 euros.</p>";
const AUDIT = {
  claims: [
    { anchor: "It was built in 1889 for the World's Fair.", kind: "incomplete", audit: true, agree: [], dissent: [
      { model: "OpenAI", kind: "incomplete", note: "Name the fair: the Exposition Universelle." }] },
    { anchor: "Tickets to the top cost 14 euros.", kind: "wrong", audit: true, agree: [], dissent: [
      { model: "Anthropic", kind: "wrong", note: "The top costs 36.10 euros.",
        source: "https://www.toureiffel.paris/en/rates", target: "14 euros" },
      { model: "OpenAI", kind: "doubtful", note: "Too low.", target: "14 euros" }] },
  ],
  unplaced: [{ model: "OpenAI", kind: "wrong", note: "Not in the answer.", quote: "It is 400 metres tall" }],
};

function marks(document) {
  return [...document.getElementById("consensusAnswerBody").querySelectorAll(".cx-claim")];
}

it("marks reviewed sentences by kind, colours the quoted words and keeps unmarked text plain", () => {
  const { window, document } = boot(ANSWER);
  const body = document.getElementById("consensusAnswerBody");
  const fallback = document.getElementById("consensusClaimsFallback");
  expect(window.renderStoredAuditMarks(body, AUDIT, fallback, [])).toBe(true);
  const [built, tickets] = marks(document);
  expect(built.textContent).toBe("It was built in 1889 for the World's Fair.");
  expect([...built.classList]).toEqual(expect.arrayContaining(["cx-claim", "is-minor", "is-audit"]));
  expect([...tickets.classList]).toEqual(expect.arrayContaining(["is-major", "is-audit", "has-spot"]));
  expect([...body.querySelectorAll(".cx-spot")].map(spot => spot.textContent)).toEqual(["14 euros"]);
  // No mark on the unmarked sentence, no green and no support counts.
  expect(marks(document)).toHaveLength(2);
  expect(body.querySelector(".is-unanimous, .claim-badge")).toBeNull();
  expect(tickets.getAttribute("role")).toBe("button");
  expect(tickets.getAttribute("aria-label")).toContain("Wrong: 2 models object");
  // A note whose passage the answer does not hold is listed below it.
  expect(fallback.hidden).toBe(false);
  expect(fallback.textContent).toContain("Other notes");
  expect(fallback.textContent).toContain("It is 400 metres tall");
});

it("opens a card with every reviewer's note, its kind and its source", () => {
  const { window, document } = boot(ANSWER);
  const body = document.getElementById("consensusAnswerBody");
  window.renderStoredAuditMarks(body, AUDIT, document.getElementById("consensusClaimsFallback"), [],
    { openNotes() { window.notesOpened = true; } });
  marks(document)[1].click();
  const pop = document.getElementById("claimPopover");
  expect(pop.hidden).toBe(false);
  const card = pop.querySelector(".cx-card-audit");
  expect(card.textContent).toContain("In the answer");
  expect(card.textContent).toContain("14 euros");
  const sides = [...card.querySelectorAll(".cx-card-side[data-kind]")];
  expect(sides.map(side => [side.dataset.kind, side.querySelector(".cx-card-claim").textContent])).toEqual([
    ["wrong", "The top costs 36.10 euros."], ["doubtful", "Too low."]]);
  expect(sides.map(side => side.querySelector(".cx-card-tag").textContent)).toEqual(["Wrong", "Doubtful"]);
  const source = card.querySelector("a.cx-card-source");
  expect(source.href).toBe("https://www.toureiffel.paris/en/rates");
  expect(source.textContent).toBe("toureiffel.paris");
  expect(sides[1].querySelector("a")).toBeNull();
  card.querySelector('.cx-card-action[data-section="differences"]').click();
  expect(window.notesOpened).toBe(true);
});

it("shows every reviewer's mark among the disagreements and only a wrong one among the contradictions", () => {
  for (const [mode, shown] of [["concerns", 2], ["all", 2], ["contradictions", 1], ["critical", 1]]) {
    const { window, document } = boot(ANSWER, mode);
    window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), AUDIT,
      document.getElementById("consensusClaimsFallback"), []);
    expect(marks(document).filter(mark => !mark.classList.contains("is-marker-filtered")).length, mode).toBe(shown);
  }
});

it("never links a source that is no web address", () => {
  const { window, document } = boot(ANSWER);
  const audit = { claims: [{ ...AUDIT.claims[1], dissent: [{ model: "OpenAI", kind: "wrong", note: "Bad link.",
    source: "javascript:alert(1)", target: "14 euros" }] }], unplaced: [] };
  window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), audit,
    document.getElementById("consensusClaimsFallback"), []);
  marks(document)[0].click();
  expect(document.querySelector("#claimPopover a.cx-card-source")).toBeNull();
  expect(document.getElementById("consensusClaimsFallback").hidden).toBe(true);
});
